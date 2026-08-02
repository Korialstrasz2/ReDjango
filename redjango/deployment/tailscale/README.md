# Accesso remoto privato con Tailscale

Questo adattatore espone ReDjango tramite Tailscale Serve senza introdurre una nuova modalità applicativa. Django continua a usare `online`; Tailscale resta un processo esterno sostituibile.

## Confine dell'adattatore

- Nessuna dipendenza Python o JavaScript da Tailscale.
- Nessuna identità Tailscale usata per autorizzare il gioco.
- Nessuna modifica al database o alla posizione dei media.
- Un solo contratto generico verso Django: `REDJANGO_PUBLIC_ORIGIN`.
- Il proxy accetta HTTPS privato sulla rete Tailscale e inoltra a `http://127.0.0.1:8003`.

## Prerequisiti

1. Installare Tailscale per Windows dal sito ufficiale.
2. Accedere e abilitare MagicDNS/HTTPS quando richiesto da `tailscale serve`.
3. Se il computer deve restare raggiungibile senza un utente collegato, scegliere **Preferences → Run unattended** dall'icona Tailscale.
4. Lasciare il computer acceso, connesso e senza sospensione.
5. Preparare account ReDjango separati e non amministrativi per i giocatori.

## Comandi

Dalla radice del progetto:

```bat
run_tailscale_plus_server.bat
```

Il file `.bat` richiede automaticamente l'elevazione Windows necessaria per
configurare Tailscale Serve e lascia aperta la finestra che ospita ReDjango.

Per uso avanzato, diagnostica o arresto:

```powershell
powershell -ExecutionPolicy Bypass -File .\redjango\deployment\tailscale\start.ps1
powershell -ExecutionPolicy Bypass -File .\redjango\deployment\tailscale\diagnose.ps1
powershell -ExecutionPolicy Bypass -File .\redjango\deployment\tailscale\stop.ps1
```

`start.ps1` rileva il nome DNS Tailscale, riusa o genera `.redjango/django-secret-key`, configura Serve e delega build, migrazioni, seed e server al launcher ufficiale `start_server.bat online`.

`Run unattended` mantiene il client Tailscale attivo dopo logout o riavvio, ma non avvia ReDjango. Dopo un riavvio bisogna rilanciare `run_tailscale_plus_server.bat`; durante l'uso normale la sua finestra deve rimanere aperta.

`stop.ps1` rimuove soltanto la pubblicazione HTTPS sulla porta 443. Non termina processi Django e non modifica dati o configurazioni Tailscale estranee.

## Giocatori

Condividere il computer dalla pagina Machines di Tailscale. Ogni giocatore installa Tailscale, accetta l'invito, apre l'URL `.ts.net` e usa il proprio account ReDjango.

## Backup

Prima di lasciare il computer incustodito, copiare in un supporto esterno o remoto:

- `db.sqlite3`
- l'intera cartella `media/`
- `.redjango/django-secret-key`

La chiave è necessaria per mantenere valide sessioni e segreti applicativi cifrati. I backup amministrativi SQLite non includono `media/`.
