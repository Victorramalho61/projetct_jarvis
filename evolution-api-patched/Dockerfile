FROM atendai/evolution-api:v2.2.3

# Patch: allow sending messages to WhatsApp LID contacts (@lid)
# Evolution API v2.2.3 blocks sends to @lid because its existence check
# returns false for LID JIDs (they are not phone numbers).
# This patch adds @lid to the bypass list alongside @broadcast and groups.
RUN node -e " \
  const fs = require('fs'); \
  let code = fs.readFileSync('/evolution/dist/main.js', 'utf8'); \
  const old = '!n.exists&&!(0,P.isJidGroup)(n.jid)&&!n.jid.includes(\"@broadcast\")'; \
  const patched = old + '&&!n.jid.includes(\"@lid\")'; \
  if (!code.includes(old)) { console.error('Pattern not found — check Evolution API version'); process.exit(1); } \
  fs.writeFileSync('/evolution/dist/main.js', code.replace(old, patched)); \
  console.log('LID patch applied'); \
"
