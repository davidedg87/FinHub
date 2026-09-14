# Piano pratico Claude Code — palestra: questo repo

Obiettivo: mettere in pratica Claude Code 101 e Claude Code in Action usando
`FinHub` come terreno di esercizio, un passo alla volta. Ogni
punto ha una guida su come portarlo a termine.

## Checklist di avanzamento

| # | Fase 1 — Claude Code 101 | Status |
|---|-------------------------|--------|
| 1 | CLAUDE.md di progetto | ✅ |
| 2 | Plan mode | ✅ |
| 3 | Diff review | ❌ |
| 4 | Ciclo git assistito | ✅ |
| 5 | Memoria persistente | ✅ |

| # | Fase 2 — Claude Code in Action | Status |
|---|--------------------------------|--------|
| 6 | MCP in pratica | ❌ |
| 7 | Subagent | ❌ |
| 8 | Hook | ✅ |
| 9 | Skill di progetto | ✅ |
| 10 | Automazione headless | ❌ |
| 11 | Code review | ❌ |

| # | Fase 3 — Corsi Anthropic | Status |
|---|-------------------------|--------|
| 12 | MCP avanzato: custom server | ❌ |
| 13 | SubAgent specializzato | ❌ |
| 14 | Agent skill articolata | ❌ |
| 15 | Integrazione MCP + SubAgent + Skill | ❌ |

**Legenda:** ✅ completato | ❌ da fare

---

## Fase 1 — Claude Code 101 (le basi)

### 1. CLAUDE.md di progetto

- Crea un file `CLAUDE.md` nella root del repo (non in `docs/`, va nella
  root perché Claude Code lo carica automaticamente all'apertura del
  progetto).
- Scrivici 3-4 regole reali e specifiche, non generiche, es.:
  - "Lo schema del DB si tocca solo via `shared/db.py`, mai query dirette
    altrove."
  - "I commit in questo repo usano l'utente git `davidedg87`, mai quello
    aziendale."
  - "I BTP si aggiornano a mano, non hanno fetch automatico."
- Verifica: apri una sessione nuova e chiedi "che convenzioni hai per
  questo progetto?" — la risposta deve rispecchiare quello che hai scritto.

### 2. Plan mode

- Premi **Shift+Tab** nel prompt per far scorrere le modalità di permesso
  finché non arrivi a "plan mode" (lo vedi indicato in basso nell'interfaccia).
- Chiedi una modifica non banale, es. "aggiungi un campo `note` alle
  holding, sia nello schema che nel form Streamlit".
- Claude esplora il codice e ti propone un piano **senza modificare nulla**.
  Leggilo, poi approvalo per farlo passare all'esecuzione (o rimandalo in
  modifica se manca qualcosa).

### 3. Diff review

- Chiedi una modifica piccola (es. "aggiungi un commento esplicativo alla
  funzione `add_holding`" o una modifica reale di una riga).
- Quando Claude propone l'edit, **non premere subito "sì a tutto"**: leggi
  il diff mostrato, poi scegli "allow once" invece di "allow always" per
  restare in controllo modifica per modifica finché non ti fidi del pattern.

### 4. Ciclo git assistito

- Chiedi in un colpo solo: "crea un branch `feature/note-field`, aggiungi
  il campo note alle holding, committa con un messaggio sensato, apri una
  PR verso master".
- Osserva la sequenza: `git checkout -b`, edit, `git add`, `git commit`,
  `gh pr create`. Guarda soprattutto se ti chiede conferma prima del push e
  della creazione della PR (azioni visibili all'esterno).
- Poi vai su `https://github.com/davidedg87/FinHub/pulls` e
  guarda la PR generata.

### 5. Memoria persistente

- Claude Code mantiene una memoria automatica per progetto in
  `~/.claude/projects/<hash-progetto>/memory/`, organizzata per tipo (user,
  feedback, project, reference).
- Chiedi esplicitamente: "ricorda che in questo repo i commit vanno sempre
  fatti con l'utente git personale, non quello aziendale."
- Chiudi la sessione, riaprila, e chiedi "che utente git devo usare per i
  commit in questo repo?" — deve rispondere corretto senza che tu lo
  ripeta.

## Fase 2 — Claude Code in Action (avanzato)

### 6. MCP in pratica

- Il server `finance-data` è già collegato (vedi `.mcp.json`). Non serve
  altro setup: parlaci in linguaggio naturale.
- Prova in sequenza: "aggiungi 10 quote di SWDA.MI comprate a 85",
  "aggiorna la quotazione di SWDA.MI", "quanto vale il mio patrimonio
  netto".
- Per vedere la lista completa dei tool esposti dal server, chiedi "che
  tool MCP hai disponibili per il portafoglio?".

### 7. Subagent

- Chiedi qualcosa che richiede di esplorare più file senza sapere già dove
  guardare, es. "trova tutti i punti del codice dove viene aggiornato il
  prezzo di una holding".
- Claude Code decide da solo se delegare a un subagent Explore (lo vedi
  comparire come uso del tool Agent). Se non lo fa spontaneamente su un
  compito ampio, puoi forzarlo: "usa un subagent per cercarlo in tutto il
  repo".
- Confronta il risultato con un tuo grep manuale: il subagent deve
  restituire una sintesi già ragionata, non solo righe grezze.

### 8. Hook

- Obiettivo: bloccare `git commit` se `tests/test_db.py` fallisce.
- Invoca la skill `/update-config` e chiedi: "aggiungi un hook che, prima
  di eseguire un comando bash che contiene `git commit`, lancia
  `tests/test_db.py` con il python del venv e blocca il commit se fallisce".
- Verifica rompendo apposta un test, prova a committare, controlla che
  l'hook lo impedisca; poi ripristina il test.

### 9. Skill di progetto

- Crea `.claude/skills/registra-spesa/SKILL.md` con frontmatter (`name`,
  `description`) e nel corpo le istruzioni: quali campi chiedere
  (importo, categoria, data), quale tool MCP chiamare (`add_transaction`),
  come confermare l'inserimento.
- Verifica invocandola con `/registra-spesa` (o chiedendo "registra una
  spesa di 50 euro per generi alimentari") e controllando che segua il
  flusso che hai scritto invece di improvvisare.

### 10. Automazione headless

- Non serve costruire un cron a mano: usa la skill `/schedule` per creare
  un agente schedulato che gira su cron (es. "ogni mattina alle 8 aggiorna
  le quotazioni ETF nel portafoglio").
- In alternativa, per un test locale immediato senza sessione interattiva,
  lancia da terminale: `claude -p "aggiorna la quotazione di SWDA.MI"` e
  osserva l'output non interattivo.

### 11. Code review

- Prima di mergiare il branch `feature/note-field` (o un altro branch di
  feature che hai aperto), lancia `/code-review` sul diff corrente.
- Leggi i finding: correttezza vs pulizia/riuso. Prova anche
  `/code-review --fix` per vedere Claude applicare da solo le correzioni
  trovate, poi rivedi comunque il diff risultante prima di accettarlo.

## Fase 3 — Corsi Anthropic (architettura avanzata)

### 12. MCP avanzato: costruire un server custom

- Obiettivo: creare un secondo MCP server (oltre `finance-data`) che espone
  strumenti per un dominio diverso, es. un server `market-data` che ritorna
  dati di mercato storici, volatilità, rating delle aziende.
- Implementa un resource provider (oltre ai semplici tool):
  una risorsa `market/symbols.json` che elenca tutti i ticker disponibili,
  opzionalmente remota (punta a un'API pubblica, con cache locale).
- Registra il nuovo server in `.mcp.json` accanto a `finance-data`.
- Test: chiedi "su quali mercati posso investire?" — l'MCP deve enumerare
  le risorse dal server appena creato.
- Approfondimento dai corsi:
  - `Introduction to ModelContextProtocol`: concetto di resource e tool,
    handshake e trasporto.
  - `ModelContext Protocol: Advanced Topics`: tool stateful, risorse
    remonte, gestione dei timeout, error recovery.

### 13. SubAgent specializzato

- Obiettivo: creare un subagent custom (non usare solo gli Explore/Plan
  integrati) che si specializza in una task specifica.
- Caso d'uso: un agent `portfolio-analyzer` che riceve uno snapshot del
  portafoglio e ritorna:
  - Allocazione per settore / geografica
  - Titoli in perdita e "days to break-even"
  - Opportunità di tax-loss harvesting
- L'agent interno (l'analyzer) usa il tool MCP `portfolio_summary` e
  analizza il risultato con logica di business, senza che l'utente debba
  dargli istruzioni passo per passo.
- Test: dal main Claude Code, chiedi "dammi un'analisi del portafoglio" e
  osserva che delega a uno subagent specializzato (non spawna un Explore).
- Approfondimento dai corsi:
  - `Introduction to SubAgents`: quando un subagent è il choice giusto;
    gestione del contesto e della memoria fra agent.
  - Paragrafi su Agent SDK per costruire agent custom con tool e logica
    propria.

### 14. Agent skill articolata

- Obiettivo: costruire una skill che non è solo un'istruzione lineare, ma
  coordina più step e gestisce fallimenti.
- Caso d'uso: skill `/rebalance-portfolio` che:
  1. Chiede all'utente il target di allocazione (es. "60% azioni, 40% bond").
  2. Recupera lo stato corrente via MCP `portfolio_summary`.
  3. Calcola le operazioni necessarie (vendi X di titolo A, compra Y di
     titolo B).
  4. Chiede conferma all'utente mostrando le operazioni.
  5. Esegue i trade via MCP `add_holding` / `delete_holding` uno per uno.
  6. Se una transazione fallisce, offre all'utente la scelta di abortire o
     riprovare la riga singola.
  7. Registra il risultato finale.
- La skill incapsula tutta questa logica: l'utente invoca `/rebalance-portfolio`
  e il wizard la guida da cima a fondo.
- Test: chiedi "ribalancia il portafoglio al 50-50 azioni-obbligazioni",
  osserva il prompt interattivo multistep, e verifica che i trade siano
  registrati in `portfolio_summary` al termine.
- Approfondimento dai corsi:
  - `Introduction to agent skills`: quando una skill supera una semplice
    lista di istruzioni; multi-step logic, error handling, stato fra step.
  - Best practice per skill che coordinano tool e decisioni dell'utente.

### 15. Integrazione: MCP + SubAgent + Skill

- Connetti i tre: la skill `/rebalance-portfolio` delega ad un subagent
  `portfolio-analyzer` per calcolare le operazioni ottimali, che a sua volta
  chiama MCP tool per recuperare dati e registrare transazioni.
- Case: "voglio spostare tutto su ETF a bassissime commissioni, ma dimmi
  prima l'impatto fiscale" → la skill chiede, il subagent analyzer calcola
  (usando le risorse MCP custom dal server market-data), e la skill esegue
  le operazioni suggerite.
- Questo è il punto dove tutte e tre le architetture (MCP, subagent,
  skill) lavorano insieme, come descritte nei tre corsi Anthropic.

## Rimandato

Worktree paralleli e CI/CD — utili quando il progetto avrà più di un
contributor o servirà isolare esperimenti in parallelo. Non ora.
