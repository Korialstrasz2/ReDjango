import socket
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from django.conf import settings
from django.core.management.base import BaseCommand


RENEWAL_MARGIN = timedelta(days=30)
CERTIFICATE_LIFETIME = timedelta(days=397)
CA_LIFETIME = timedelta(days=3650)


def _identities() -> tuple[set[str], set[str]]:
    dns_names = {"localhost", socket.gethostname()}
    ip_addresses = {"127.0.0.1", "::1"}
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None):
            if result[4] and result[4][0]:
                ip_addresses.add(str(ip_address(result[4][0].split("%", 1)[0])))
    except (socket.gaierror, ValueError):
        pass
    return dns_names, ip_addresses


def _load_certificate_and_key(certificate_path: Path, key_path: Path):
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if private_key.public_key().public_numbers() != certificate.public_key().public_numbers():
        raise ValueError("Certificate and private key do not match.")
    return certificate, private_key


def _ca_is_current(certificate_path: Path, key_path: Path) -> bool:
    if not certificate_path.is_file() or not key_path.is_file():
        return False
    try:
        certificate, _private_key = _load_certificate_and_key(
            certificate_path,
            key_path,
        )
        constraints = certificate.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
        return (
            constraints.ca
            and certificate.issuer == certificate.subject
            and certificate.not_valid_after_utc > datetime.now(UTC) + RENEWAL_MARGIN
        )
    except (OSError, TypeError, ValueError, x509.ExtensionNotFound):
        return False


def _server_certificate_is_current(
    certificate_path: Path,
    key_path: Path,
    ca_certificate: x509.Certificate,
    dns_names: set[str],
    ip_addresses: set[str],
) -> bool:
    if not certificate_path.is_file() or not key_path.is_file():
        return False
    try:
        certificate, _private_key = _load_certificate_and_key(
            certificate_path,
            key_path,
        )
        if certificate.not_valid_after_utc <= datetime.now(UTC) + RENEWAL_MARGIN:
            return False
        if certificate.issuer != ca_certificate.subject:
            return False
        ca_certificate.public_key().verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            padding.PKCS1v15(),
            certificate.signature_hash_algorithm,
        )
        alternative_names = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        stored_dns = set(alternative_names.get_values_for_type(x509.DNSName))
        stored_ips = {
            str(value)
            for value in alternative_names.get_values_for_type(x509.IPAddress)
        }
        return dns_names <= stored_dns and ip_addresses <= stored_ips
    except (
        InvalidSignature,
        OSError,
        TypeError,
        ValueError,
        x509.ExtensionNotFound,
    ):
        return False


def _fingerprint(certificate_path: Path) -> str:
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    digest = certificate.fingerprint(hashes.SHA256())
    return ":".join(f"{byte:02X}" for byte in digest)


def _write_private_key(key_path: Path, private_key) -> None:
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


class Command(BaseCommand):
    help = "Crea o rinnova il certificato HTTPS autofirmato per la modalità LAN."

    def handle(self, *args, **options):
        tls_directory = Path(settings.BASE_DIR) / ".redjango" / "tls"
        tls_directory.mkdir(parents=True, exist_ok=True)
        ca_certificate_path = tls_directory / "lan-ca.pem"
        ca_key_path = tls_directory / "lan-ca-key.pem"
        certificate_path = tls_directory / "lan-cert.pem"
        key_path = tls_directory / "lan-key.pem"
        dns_names, ip_addresses = _identities()

        ca_created = False
        if not _ca_is_current(ca_certificate_path, ca_key_path):
            ca_private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
            ca_subject = x509.Name([
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ReDjango locale"),
                x509.NameAttribute(
                    NameOID.COMMON_NAME,
                    f"ReDjango LAN CA - {socket.gethostname()}",
                ),
            ])
            now = datetime.now(UTC)
            ca_certificate = (
                x509.CertificateBuilder()
                .subject_name(ca_subject)
                .issuer_name(ca_subject)
                .public_key(ca_private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5))
                .not_valid_after(now + CA_LIFETIME)
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=0),
                    critical=True,
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=True,
                        crl_sign=True,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(
                        ca_private_key.public_key()
                    ),
                    critical=False,
                )
                .sign(ca_private_key, hashes.SHA256())
            )
            _write_private_key(ca_key_path, ca_private_key)
            ca_certificate_path.write_bytes(
                ca_certificate.public_bytes(serialization.Encoding.PEM)
            )
            ca_created = True
        else:
            ca_certificate, ca_private_key = _load_certificate_and_key(
                ca_certificate_path,
                ca_key_path,
            )

        if ca_created or not _server_certificate_is_current(
            certificate_path,
            key_path,
            ca_certificate,
            dns_names,
            ip_addresses,
        ):
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = x509.Name([
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ReDjango locale"),
                x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname()),
            ])
            now = datetime.now(UTC)
            alternative_names = [
                *(x509.DNSName(name) for name in sorted(dns_names)),
                *(x509.IPAddress(ip_address(value)) for value in sorted(ip_addresses)),
            ]
            certificate = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(ca_certificate.subject)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5))
                .not_valid_after(now + CERTIFICATE_LIFETIME)
                .add_extension(x509.SubjectAlternativeName(alternative_names), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=True,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                    critical=False,
                )
                .add_extension(
                    x509.AuthorityKeyIdentifier.from_issuer_public_key(
                        ca_private_key.public_key()
                    ),
                    critical=False,
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                    critical=False,
                )
                .sign(ca_private_key, hashes.SHA256())
            )
            _write_private_key(key_path, private_key)
            certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
            self.stdout.write(self.style.SUCCESS("Certificato HTTPS LAN creato o rinnovato."))
        else:
            self.stdout.write("Certificato HTTPS LAN già valido.")

        # The CA fingerprint lets clients establish trust once even if DHCP
        # causes the leaf certificate to be regenerated.
        self.stdout.write(f"CA SHA-256: {_fingerprint(ca_certificate_path)}")
        self.stdout.write(f"CA da installare sui client: {ca_certificate_path}")
