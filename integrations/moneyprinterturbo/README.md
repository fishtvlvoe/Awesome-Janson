# MoneyPrinterTurbo provider

MoneyPrinterTurbo is an optional **topic/script → stock-material/TTS/BGM video** provider.
It is not used to replace Awesome-Janson's long-recording semantic editor.

## Routing

- Existing long recording / workshop / talking-head footage → Awesome-Janson + talking-head adapter.
- Topic, keyword or finished script with generated narration and stock footage → MoneyPrinterTurbo provider.
- Local assets can be passed to MoneyPrinterTurbo only when the user explicitly requests generated-narration compositing.

Only the upstream Agent Skill and safe installation helper are vendored here. The full upstream app is installed on demand by the helper and remains outside the Awesome-Janson repository.

From Awesome-Janson, preview the provider command without installing anything:

```bash
python3 scripts/moneyprinterturbo_provider.py --subject "你的主題"
```

Add `--run` only for an explicit topic-to-video job.

The helper can call LLM, TTS, stock-material, music and cross-posting providers. Those capabilities are opt-in and require the user's own configuration/API keys; Awesome-Janson never prints or copies those secrets.
