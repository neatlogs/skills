# Step 1: Install neatlogs (latest)

1. Call `detect_package_manager`.
2. Install LATEST neatlogs + openai. Hermes is NOT on PyPI — it's installed from
   GitHub, so don't try to `pip install hermes-agent` from the index:
   - pip: `pip install --upgrade neatlogs openai`
   - uv: `uv add --upgrade neatlogs openai`
   - poetry: `poetry add neatlogs@latest openai`
3. Hermes itself (if not already present) is git-installed:
   `pip install "git+https://github.com/NousResearch/hermes-agent.git"`
   (needs Python >= 3.11).
4. Background install; continue.
