---
name: registra-spesa
description: Registra una spesa o un'entrata nel database del portafoglio. Usala quando l'utente dice di aver speso o incassato qualcosa, o chiede di segnare un movimento.
---

# Registra spesa

Scrive un movimento nella tabella `transactions` del profilo attivo, col tool MCP
`add_transaction` (server `finance-data`).

## 1. Raccogli i campi

| Campo | Valore |
|---|---|
| `amount` | Numero **sempre positivo**, in euro. È `type` a distinguere spesa da entrata, non il segno. |
| `category` | Testo libero — vedi il punto 2, è il campo che si rovina più facilmente. |
| `date` | `YYYY-MM-DD`. Se l'utente non la dice, è oggi. Le date relative ("ieri", "lunedì scorso") convertile tu. |
| `type` | `expense` per una spesa, `income` per un'entrata. Solo questi due valori: il DB rifiuta il resto. |
| `description` | Opzionale, il dettaglio in chiaro: "Esselunga", "rimborso trasferta". |

Chiedi in un colpo solo i campi che mancano davvero, non uno alla volta, e lascia stare quelli
che l'utente ha già dichiarato.

## 2. Riusa una categoria esistente

`category` è testo libero, nessun enum a vincolarlo: la deriva di grafia è il difetto più
probabile di questo flusso. "Spesa", "spesa", "Supermercato" e "Alimentari" diventano quattro
categorie distinte, e il riepilogo per categoria smette di dire qualcosa.

Prima di scrivere chiama `list_transactions` e guarda le categorie già in uso. Se una calza,
riusala con la **stessa identica grafia**. Se nessuna calza, creane una nuova e dillo nella
conferma.

## 3. Verifica quello che hai dedotto

Una transazione sbagliata si corregge con `update_transaction` e si cancella con
`delete_transaction`, ma servono l'`id`: se l'utente se ne accorge fra un mese, ritrovarla in
mezzo a centinaia di righe importate non è gratis.

Quindi, se hai dedotto un campo che l'utente non ha detto esplicitamente — la categoria, una data
relativa, il tipo — mettiglielo davanti in una riga e aspetta l'ok. Se ha dichiarato tutto lui,
scrivi e basta.

## 4. Scrivi e conferma

Chiama `add_transaction`: restituisce l'`id` della riga creata.

Conferma riepilogando quello che è finito nel database, `id` compreso:

> Registrata #42 — 50,00 € · Alimentari · 2026-09-14 (spesa)

Se hai dedotto o normalizzato qualcosa, dillo qui: `categoria nuova "Alimentari"`, oppure
`"ieri" → 2026-09-13`. È l'ultimo punto in cui l'utente può accorgersi di un errore mentre
rimediare è ancora facile.
