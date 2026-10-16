# Public Web Demo

Streamlit UI: `streamlit run streamlit_app.py`

This is an **isolated mock-mode read-only demonstration**. It executes the existing
LangGraph agent in a fresh temporary SQLite database for each input. No private
employee data is accessed. External email, persistent writes and OpenAI calls are
disabled. Every turn is independently seeded, so multi-turn memory is not
demonstrated in this public interface. Refer to `main.py` for the CLI multi-turn
and human-approval implementation.

To deploy, connect this repository in Streamlit Community Cloud, choose
`streamlit_app.py`, and use `web_requirements.txt` only if configuring a custom
requirements installation. The platform defaults to root `requirements.txt` which
already contains LangGraph and the optional dependencies. Install Streamlit separately
or include it in the root requirements. This change adds Streamlit to the root
requirements so standard deployment discovers it.

No API key is needed for the public mock mode.
