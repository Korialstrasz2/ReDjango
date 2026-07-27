# Icone degli effetti

Le 86 icone storiche dedicate agli effetti sono conservate in `elder/` come
PNG, con il loro slug Elder Django originale (per esempio `pf_extra.png` e
`res_fuoco_extra.png`). Il catalogo server le espone tutte nel selettore e
collega automaticamente le statistiche ReDjango all'icona Elder equivalente.

Inserire qui le icone WebP quadrate degli effetti. Il nome del file deve
corrispondere esattamente al nome visibile dell'icona nel catalogo, per esempio:

```text
Runa arcana.webp
Fiamma.webp
Cristallo di gelo.webp
```

Quando il file è presente viene mostrato al posto del glifo SVG incorporato;
se manca o non può essere caricato, l'interfaccia mantiene automaticamente il
glifo come fallback.
