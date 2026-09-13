"""Inspector locale per il server MCP Python del progetto.

Avvio:
streamlit run dashboard/mcp_inspector.py
"""
import inspect
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import server as mcp_server  # noqa: E402


def _discover_tools() -> dict[str, dict[str, str]]:
    tools: dict[str, dict[str, str]] = {}
    for name, fn in inspect.getmembers(mcp_server, inspect.isfunction):
        if fn.__module__ != "mcp_server.server":
            continue
        if name.startswith("_"):
            continue

        tools[name] = {
            "signature": str(inspect.signature(fn)),
            "doc": inspect.getdoc(fn) or "Nessuna descrizione disponibile.",
        }

    return tools


def _invoke_tool(tool_name: str, payload: str) -> tuple[bool, object]:
    try:
        args = json.loads(payload.strip() or "{}")
    except json.JSONDecodeError as ex:
        return False, f"JSON non valido: {ex}"

    if not isinstance(args, dict):
        return False, "Il payload deve essere un oggetto JSON (chiave/valore)."

    fn = getattr(mcp_server, tool_name, None)
    if fn is None or not callable(fn):
        return False, f"Tool non trovato: {tool_name}"

    try:
        result = fn(**args)
        return True, result
    except Exception as ex:  # noqa: BLE001
        details = "\n".join(traceback.format_exception(ex))
        return False, details


def _init_state() -> None:
    if "call_history" not in st.session_state:
        st.session_state.call_history = []


def _render_header() -> None:
    st.set_page_config(page_title="MCP Inspector Locale", layout="wide")
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
          html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
          .mono { font-family: 'IBM Plex Mono', monospace; font-size: 0.92rem; }
          .hero {
            background: linear-gradient(125deg, #f7efe2 0%, #d6ece5 40%, #cddcf7 100%);
            border: 1px solid #a7b6d6;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
          }
          .hint {
            border-left: 4px solid #14532d;
            background: #f0fdf4;
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hero">
          <h2 style="margin:0 0 0.35rem 0;">MCP Inspector Locale</h2>
          <div style="margin:0;">Interfaccia per esplorare e testare i tool del server <span class="mono">mcp_server/server.py</span>.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_tool_panel(tools: dict[str, dict[str, str]]) -> None:
    col_left, col_right = st.columns([1.05, 1.35], gap="large")

    with col_left:
        st.subheader("Server")
        st.write("Nome: finance-data")
        st.write(f"Tool disponibili: {len(tools)}")
        st.caption("La lista e le firme sono lette direttamente dal modulo Python.")

        st.subheader("Selezione tool")
        tool_name = st.selectbox("Tool", options=sorted(tools.keys()), key="tool_name")
        info = tools[tool_name]
        st.markdown("Firma")
        st.markdown(f"<div class='mono'>{tool_name}{info['signature']}</div>", unsafe_allow_html=True)
        st.markdown("Descrizione")
        st.write(info["doc"])

    with col_right:
        st.subheader("Invocazione")
        payload_example = "{}"
        payload = st.text_area(
            "Argomenti JSON",
            value=payload_example,
            height=220,
            help="Inserisci un oggetto JSON con i parametri del tool.",
            key="payload",
        )
        invoke = st.button("Esegui tool", use_container_width=True, type="primary")

        st.markdown(
            """
            <div class="hint">
              Consiglio: se un tool non richiede parametri, usa semplicemente {}.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if invoke:
            ok, result = _invoke_tool(tool_name, payload)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.call_history.insert(
                0,
                {
                    "timestamp": stamp,
                    "tool": tool_name,
                    "payload": payload,
                    "ok": ok,
                    "result": result,
                },
            )

            if ok:
                st.success("Esecuzione completata")
                st.json(result)
            else:
                st.error("Esecuzione fallita")
                st.code(str(result), language="text")


def _render_history() -> None:
    st.subheader("Storico chiamate")
    if not st.session_state.call_history:
        st.info("Nessuna chiamata eseguita in questa sessione.")
        return

    for item in st.session_state.call_history:
        title = f"{item['timestamp']} | {item['tool']} | {'OK' if item['ok'] else 'ERRORE'}"
        with st.expander(title, expanded=False):
            st.markdown("Payload")
            st.code(item["payload"], language="json")
            st.markdown("Risultato")
            if item["ok"]:
                st.json(item["result"])
            else:
                st.code(str(item["result"]), language="text")


def main() -> None:
    _init_state()
    _render_header()
    tools = _discover_tools()
    if not tools:
        st.error("Nessun tool rilevato in mcp_server.server")
        return

    _render_tool_panel(tools)
    st.divider()
    _render_history()


if __name__ == "__main__":
    main()