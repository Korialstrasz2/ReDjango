# Ritratti dei personaggi

Questa cartella contiene le varianti mostrate nella modalità equipaggiamento **Sagoma**.

Il nome file preferito è `<personaggio>_<armatura>.webp`, per esempio:

```text
livia_cuoio.webp
razirr_elfico.webp
illaoi_veste-a.webp
```

Se non esiste una variante per l'armatura, ReDjango cerca `<personaggio>_base.webp`.
Sono accettati anche file `.png`, così le immagini del progetto originale possono essere riutilizzate senza conversione. In assenza di entrambe le varianti viene mostrato `../placeholder.svg`.

La chiave del personaggio è il primo nome normalizzato in minuscolo. La chiave dell'armatura deriva dal secondo tipo dell'armatura equipaggiata; le vesti mantengono le varianti legacy `veste-gm`, `veste-m`, `veste-e`, `veste-q`, `veste-a` e `veste-p`.

Per nomi ambigui o rinominabili si può impostare `metadata.appearanceKey` sul personaggio. Per una variante speciale si può impostare `metadata.appearanceArmorKey` sull'oggetto armatura o veste.
