# Finance data-only publisher

publish-finance-digest.yml receives canonical public JSON, publication week,
SHA-256 and expected public main SHA. It receives no private Codex session or
private repository credentials. The receive command requires --series finance;
existing research intake remains unchanged.

The Python envelope/type/secret checks do not alone approve publication.
The live blog /api/finance-digests/validate must approve the exact raw bytes.
Publication creates one immutable finance-YYYY-MM-DD release containing
weekly-digest.json; existing content cannot be replaced. The blog independently
verifies the attestation and imports it through staging and production gates.

Research quality policy lives at
https://www.hyoyoul.com/posts/weekly-earnings-editorial-policy.
The source-backed draft and separate AI review happen privately, not in this
publisher. Machine checks are not an audit, investment advice or proof of returns.
No extra compute provider is configured here.
