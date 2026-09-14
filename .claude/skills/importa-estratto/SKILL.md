---
name: importa-estratto
description: Importa un estratto conto o una lista movimenti da file (CSV) nel portafoglio. Usala quando l'utente dice di aver scaricato un estratto, chiede di caricare i movimenti di un conto, o nomina un file da importare.
---

# Importa estratto

Porta i movimenti di un file dentro `transactions`, col tool MCP `import_transactions_file`
(server `finance-data`). L'import e **idempotente**: reimportare lo stesso file non duplica
niente, quindi rilanciarlo dopo un errore e sicuro.

Il rischio qui non e sbagliare una riga: e scrivere centinaia di righe nel posto sbagliato.
Il flusso sotto esiste per quello.

## 1. Raccogli i quattro campi

| Campo | Come ottenerlo |
|---|---|
| `path` | Il percorso del file. Se l'utente nomina un file senza percorso, chiedi dove sta invece di indovinare. |
| `formato` | Chiama `list_import_formats`. Se ce n'e uno solo e plausibile, usalo e dillo. |
| `conto` | Il conto di destinazione. Chiama `list_cash_accounts` e **riusa un nome esistente con la stessa identica grafia**: "ING", "Conto ING" e "conto ing" diventano tre conti distinti e i movimenti si sparpagliano. |
| `profilo` | Chiama `get_active_profile`. Non passarlo mai a caso: il tool lo rifiuta se non esiste, ma non puo accorgersi se e semplicemente il profilo sbagliato. |

Chiedi in un colpo solo quello che manca davvero.

## 2. Dichiara il profilo e fermati

Prima di scrivere qualunque cosa, metti davanti all'utente una riga sola:

> Importo `estratto-gennaio.csv` (formato `generico`) nel conto **Conto ING**, profilo **Davide Di Gregorio**. Procedo?

E aspetta. Questo passaggio non e cortesia: il server MCP e un processo diverso dalla
dashboard e non vede i cambi di profilo fatti li, quindi il profilo che stai per usare puo
non essere quello che l'utente ha davanti sullo schermo. Un'import nel profilo sbagliato si
disfa solo riga per riga.

Se l'utente ha gia detto esplicitamente conto e profilo nella sua richiesta, la conferma non
serve: procedi.

## 3. Importa

Chiama `import_transactions_file(path, formato, conto, profilo)`. Ritorna:

```
{"profilo": ..., "inserite": N, "duplicate": N, "scartate": [{"riga": ..., "motivo": ...}]}
```

Se solleva, il messaggio dice gia cosa non va (formato sconosciuto, profilo inesistente,
file illeggibile). Riportalo e correggi il campo sbagliato: non ritentare identico.

## 4. Riferisci, in questo ordine

1. **Cosa e entrato e dove**: `12 movimenti in Conto ING (profilo Davide Di Gregorio)`.
2. **Le duplicate**, se ce ne sono, spiegando che non sono un errore: erano gia a database
   da un import precedente, e sono state saltate apposta.
3. **Le scartate**, se ce ne sono — vedi sotto.

Se `inserite` e 0 e `duplicate` e alto, quel file era gia stato importato: dillo chiaramente,
invece di lasciare che sembri un fallimento.

## 5. Le righe scartate, una per una

Ogni riga scartata ha un `motivo`. Non liquidarle con un conteggio: mostra la riga e il
motivo, e proponi la correzione.

- **`data non interpretabile`** — quasi sempre il tracciato usa un formato di data che il
  parser non conosce. Se **tutte** le righe sono scartate cosi, non e un problema del file:
  e il parser sbagliato, o ne serve uno nuovo per quella banca. Dillo invece di far
  correggere l'estratto a mano.
- **`importo non interpretabile`** — spesso una colonna vuota o un totale di sezione finito
  fra i movimenti. Se e un totale, va ignorato, non corretto.
- **`importo a zero`** — di solito righe informative della banca, non movimenti. Ignorabili.

Se le righe da correggere sono poche e l'utente vuole recuperarle, si inseriscono con
`add_transaction` una alla volta, non riscrivendo il file.

## 6. Poi

Offri, senza farlo di tua iniziativa: *"vuoi che guardi com'e cambiato il patrimonio?"* — e
se l'utente dice di si, delega a `portfolio-analyzer`.

Non toccare `set_cash_balance`: l'import porta i **movimenti**, non il saldo. Il saldo e una
fotografia che arriva dall'estratto e si imposta a parte; sommare i movimenti al saldo
conterebbe due volte gli stessi soldi.
