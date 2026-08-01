# Guida LLM — Revisione rarità degli oggetti 2, 3 e 4

## Obiettivo e confini

Revisiona ogni `Oggetto` la cui `rarita` attuale è `2`, `3` o `4` e proponi una
nuova rarità per ciascuno. Il risultato è una proposta editoriale: **non
modificare il database**, non cambiare i campi dell'oggetto e non rigenerare i
negozi. Un umano approva poi le modifiche tramite l'editor o una migrazione
esplicita.

La scala ha questo significato operativo:

| Rarità | Significato |
|---:|---|
| 0 | `Unico`: assegnato a mano, mai generato nei negozi. |
| 1 | Comune e facilmente reperibile per il suo livello di loot. |
| 2 | Non comune: normale, ma non presente in ogni negozio. |
| 3 | Raro: distintivo, potente o costoso; deve apparire saltuariamente. |
| 4 | Molto raro: alto impatto, alto valore o identità forte; destinato ai negozi/loot alti. |
| 5 | Eccezionale ma acquistabile: accesso estremamente limitato, non un oggetto unico. |

`rarita` misura la reperibilità nel mercato, non soltanto prezzo, potenza o
prestigio narrativo. Un oggetto che dovrebbe essere una ricompensa singolare
va proposto a `0`, anche se oggi è 2–4.

## Dati da leggere per ogni oggetto

Parti da tutte le righe con `rarita__in=[2, 3, 4]`, senza limitare a una pagina.
Per ogni riga leggi e conserva nel report almeno: `id`, `nome`, `rarita`,
`modello`, `temporaneo`, `archiviato`, `archived_at`, `speciale`, `valore`,
`peso`, `tipo_1`–`tipo_4`, `tipo_arma`, `pa_per_attacco`, `lv_loot`,
`regione_loot`, `peso_regione`, `descrizione`, `effetto_1`–`effetto_8`,
`regole_speciali`, `effects`, `weapon_profile` e `metadata`.

Leggi inoltre la configurazione del Mercato: probabilità per rarità, tipi di
negozio e relativi `itemTypeRanks`, regole di prezzo, copie massime, regioni e
livelli. Per ogni oggetto determina se sia realmente vendibile oggi: deve essere
un `modello`, non archiviato, non `speciale`, con `lv_loot` valido e `tipo_1`
abilitato con rank inferiore a 5 in almeno un tipo di negozio. Segnala gli
oggetti non vendibili, ma non fingere che la rarità da sola li renda vendibili.

## Metodo obbligatorio

1. Valuta prima l'identità: oggetto comune, componente, arma/armatura normale,
   magico distintivo, artefatto, ricompensa narrativa o placeholder di sistema.
2. Confrontalo con oggetti dello stesso `tipo_1`, stesso intervallo `lv_loot` e
   stessa funzione; non confrontare una pozione con una spada solo in base al
   valore.
3. Considera insieme valore base, potenza meccanica degli effetti, danno/PA,
   peso, capacità o utilità, disponibilità regionale e range di loot. Un alto
   valore può giustificare una rarità superiore, ma non deve dominare un effetto
   debole o un consumabile ordinario.
4. Tieni conto della pressione del mercato: un tipo presente in molti negozi o
   con rank basso appare molto più spesso; un oggetto regionale con
   `peso_regione` elevato è ancora più comune nella propria regione.
5. Controlla duplicati, varianti in progressione (per esempio munizioni +1/+2),
   set, nomi singolari e oggetti a tema. Le progressioni devono crescere in modo
   coerente salvo una motivazione esplicita.
6. Se un effetto, una descrizione o una regola è ambiguo, non inventarne il
   funzionamento: marca `needsHumanReview=true`, conserva la rarità attuale se
   non esiste un motivo forte per cambiare, e spiega il dubbio.
7. Proponi `0` solo per veri premi assegnati a mano; proponi `5` solo se può
   restare acquistabile, pur essendo eccezionale. Non usare 0 o 5 come scorciatoia
   per dati incompleti.

## Formato di consegna

Restituisci un record per **ogni** oggetto analizzato, ordinato per `id`, in JSON
valido dentro un unico blocco di codice. Non omettere gli oggetti invariati.

```json
{
  "scope": {"currentRarities": [2, 3, 4], "reviewedCount": 0},
  "summary": {
    "proposedCounts": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    "needsHumanReviewCount": 0,
    "marketIneligibleCount": 0
  },
  "proposals": [
    {
      "id": 123,
      "name": "Nome esatto",
      "currentRarity": 3,
      "proposedRarity": 2,
      "confidence": "high",
      "needsHumanReview": false,
      "marketEligible": true,
      "comparables": [456, 789],
      "reasons": [
        "Valore e utilità coerenti con gli altri oggetti di tipo X al livello Y.",
        "Il rank nei negozi e la disponibilità regionale rendono 3 eccessivo."
      ],
      "warnings": []
    }
  ]
}
```

Le `reasons` devono riferirsi a dati concreti dell'oggetto e a confronti reali.
Usa `confidence` `high`, `medium` o `low`. Prima del JSON, scrivi al massimo un
paragrafo con i pattern osservati e le decisioni che richiedono conferma umana.
