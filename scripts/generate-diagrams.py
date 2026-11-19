#!/usr/bin/env python3
"""Generate publication-grade SVG diagrams for Ravenhelm Release Operations Methodology (RROM).

Generates both Dark Mode (Obsidian) and Print Mode (Bone) editions.
"""
import os

DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diagrams")
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

PALETTES = {
    "dark": {
        "bg": "#0B0C0E",
        "card_bg": "#14171C",
        "card_border": "#2B303A",
        "text_primary": "#EDE8DC",
        "text_secondary": "#8E939B",
        "text_muted": "#5A606A",
        "accent": "#A3222F",      # Garnet
        "gold": "#C4A45A",        # Warm Brass
        "cyan": "#4DA8DA",        # Ice Blue / Active
        "green": "#4E9A51",       # Verified Green
        "arrow": "#8E939B"
    },
    "print": {
        "bg": "#EDE8DC",
        "card_bg": "#E2DDD1",
        "card_border": "#B0A898",
        "text_primary": "#0B0C0E",
        "text_secondary": "#6F6A62",
        "text_muted": "#8A847A",
        "accent": "#A3222F",
        "gold": "#96752C",
        "cyan": "#1F6E94",
        "green": "#2E6B31",
        "arrow": "#6F6A62"
    }
}

def generate_diagram_1(edition):
    """Diagram 1: The Core Axiom (Build vs Release vs Deploy)"""
    p = PALETTES[edition]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 380" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 20px; font-weight: 600; fill: {p['text_primary']}; }}
      .subtitle {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['text_secondary']}; letter-spacing: 0.12em; }}
      .phase-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 600; fill: {p['text_primary']}; }}
      .body-text {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; fill: {p['text_secondary']}; }}
      .code-text {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['cyan']}; }}
      .accent-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; fill: {p['accent']}; font-weight: 600; letter-spacing: 0.08em; }}
      .gold-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; fill: {p['gold']}; font-weight: 600; letter-spacing: 0.08em; }}
      .green-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; fill: {p['green']}; font-weight: 600; letter-spacing: 0.08em; }}
    </style>
    <marker id="arrow-{edition}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="{p['arrow']}"/>
    </marker>
  </defs>

  <!-- Background -->
  <rect width="100%" height="100%" fill="{p['bg']}" rx="8"/>

  <!-- Header -->
  <text x="40" y="45" class="title">The Core Axiom: Three Lifecycle Boundaries</text>
  <text x="40" y="68" class="subtitle">BUILDS ARE THE UNIT · RELEASES ARE NAMES · DEPLOYS ARE RECONCILIATIONS</text>

  <!-- Phase 1: BUILD -->
  <g transform="translate(40, 100)">
    <rect width="250" height="230" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <rect x="0" y="0" width="250" height="32" rx="6" fill="{p['card_border']}" opacity="0.3"/>
    <text x="16" y="22" class="accent-badge">PHASE 1 · ONCE ONLY</text>
    <text x="16" y="58" class="phase-title">1. The Build (Unit)</text>
    <text x="16" y="80" class="subtitle">TRIGGER: MERGE TO MAIN</text>
    <text x="16" y="112" class="body-text">Compiles code, runs tests, and</text>
    <text x="16" y="130" class="body-text">builds the single immutable artifact.</text>
    <line x1="16" y1="150" x2="234" y2="150" stroke="{p['card_border']}" stroke-width="1"/>
    <text x="16" y="174" class="code-text">tag: :b&lt;N&gt; (monotonic)</text>
    <text x="16" y="196" class="code-text">tag: :sha-&lt;commit12&gt;</text>
    <text x="16" y="218" class="code-text">digest: sha256:7f9a...3c</text>
  </g>

  <!-- Transition 1 -> 2 Arrow -->
  <line x1="300" y1="215" x2="335" y2="215" stroke="{p['arrow']}" stroke-width="1.8" marker-end="url(#arrow-{edition})"/>

  <!-- Phase 2: RELEASE -->
  <g transform="translate(345, 100)">
    <rect width="250" height="230" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <rect x="0" y="0" width="250" height="32" rx="6" fill="{p['card_border']}" opacity="0.3"/>
    <text x="16" y="22" class="gold-badge">PHASE 2 · ZERO REBUILDS</text>
    <text x="16" y="58" class="phase-title">2. The Release (Name)</text>
    <text x="16" y="80" class="subtitle">TRIGGER: RELEASE PR + TAG</text>
    <text x="16" y="112" class="body-text">Assigns SemVer metadata to an</text>
    <text x="16" y="130" class="body-text">existing build. Zero source drift.</text>
    <line x1="16" y1="150" x2="234" y2="150" stroke="{p['card_border']}" stroke-width="1"/>
    <text x="16" y="174" class="code-text">git tag: v1.0.3</text>
    <text x="16" y="196" class="code-text">values: pin sha256:7f9a...</text>
    <text x="16" y="218" class="code-text">harbor: retag b&lt;N&gt; -&gt; v1.0.3</text>
  </g>

  <!-- Transition 2 -> 3 Arrow -->
  <line x1="605" y1="215" x2="640" y2="215" stroke="{p['arrow']}" stroke-width="1.8" marker-end="url(#arrow-{edition})"/>

  <!-- Phase 3: DEPLOY -->
  <g transform="translate(650, 100)">
    <rect width="210" height="230" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <rect x="0" y="0" width="210" height="32" rx="6" fill="{p['card_border']}" opacity="0.3"/>
    <text x="16" y="22" class="green-badge">PHASE 3 · CONVERGENCE</text>
    <text x="16" y="58" class="phase-title">3. The Deploy</text>
    <text x="16" y="80" class="subtitle">TRIGGER: DECLARATIVE SYNC</text>
    <text x="16" y="112" class="body-text">Argo CD / Brew / OTA</text>
    <text x="16" y="130" class="body-text">pulls the pinned digest.</text>
    <line x1="16" y1="150" x2="194" y2="150" stroke="{p['card_border']}" stroke-width="1"/>
    <text x="16" y="174" class="code-text">run: image@sha256:...</text>
    <text x="16" y="196" class="body-text">Probe: /api/health</text>
    <text x="16" y="218" class="green-badge">STATUS: VERIFIED LIVE</text>
  </g>
</svg>'''
    with open(os.path.join(DIAGRAMS_DIR, f"diagram1-core-axiom-{edition}.svg"), "w") as f:
        f.write(svg)

def generate_diagram_2(edition):
    """Diagram 2: Multi-Surface Release Rails (Rail A, B, C)"""
    p = PALETTES[edition]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 440" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 20px; font-weight: 600; fill: {p['text_primary']}; }}
      .subtitle {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['text_secondary']}; letter-spacing: 0.12em; }}
      .rail-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 15px; font-weight: 600; fill: {p['text_primary']}; }}
      .body-text {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 11.5px; fill: {p['text_secondary']}; }}
      .code-text {{ font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; fill: {p['cyan']}; }}
      .hub-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 17px; font-weight: 600; fill: {p['text_primary']}; }}
      .rail-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.08em; }}
    </style>
    <marker id="arrow2-{edition}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="{p['arrow']}"/>
    </marker>
  </defs>

  <rect width="100%" height="100%" fill="{p['bg']}" rx="8"/>

  <!-- Header -->
  <text x="40" y="45" class="title">The Three Multi-Surface Release Rails</text>
  <text x="40" y="68" class="subtitle">UNIFIED DISPATCH ACROSS CLUSTER · WORKSTATION · DESKTOP</text>

  <!-- Central Source / CI Hub -->
  <g transform="translate(40, 110)">
    <rect width="220" height="280" rx="6" fill="{p['card_bg']}" stroke="{p['accent']}" stroke-width="1.6"/>
    <text x="20" y="32" class="rail-badge" fill="{p['accent']}">SOURCE &amp; BUILD HUB</text>
    <text x="20" y="62" class="hub-title">Source of Truth</text>
    <text x="20" y="84" class="subtitle">FORGEJO / GITHUB</text>
    
    <text x="20" y="120" class="body-text">Push to main triggers:</text>
    <text x="20" y="142" class="code-text">.forgejo/workflows/build.yml</text>
    
    <line x1="20" y1="165" x2="200" y2="165" stroke="{p['card_border']}" stroke-width="1"/>
    
    <text x="20" y="195" class="hub-title" style="font-size: 14px;">OCI Registry (Harbor)</text>
    <text x="20" y="220" class="code-text">:b&lt;N&gt; (Build ID)</text>
    <text x="20" y="242" class="code-text">:sha-&lt;commit12&gt;</text>
    <text x="20" y="264" class="code-text">@sha256:&lt;digest&gt;</text>
  </g>

  <!-- Connectors to Rails -->
  <path d="M 260 170 C 310 170, 310 150, 360 150" fill="none" stroke="{p['arrow']}" stroke-width="1.6" marker-end="url(#arrow2-{edition})"/>
  <path d="M 260 250 C 310 250, 310 250, 360 250" fill="none" stroke="{p['arrow']}" stroke-width="1.6" marker-end="url(#arrow2-{edition})"/>
  <path d="M 260 330 C 310 330, 310 350, 360 350" fill="none" stroke="{p['arrow']}" stroke-width="1.6" marker-end="url(#arrow2-{edition})"/>

  <!-- Rail A: Server GitOps -->
  <g transform="translate(370, 100)">
    <rect width="490" height="90" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <text x="18" y="26" class="rail-badge" fill="{p['cyan']}">RAIL A · SERVER / K3S CLUSTER GITOPS</text>
    <text x="18" y="52" class="rail-title">Harbor OCI + Argo CD (norns-gitops) · Reference: Vitki</text>
    <text x="18" y="74" class="body-text">GitOps repository pins immutable digest · Argo CD reconciles cluster pods without laptop access</text>
  </g>

  <!-- Rail B: Workstation Homebrew -->
  <g transform="translate(370, 205)">
    <rect width="490" height="90" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <text x="18" y="26" class="rail-badge" fill="{p['gold']}">RAIL B · DEVELOPER WORKSTATION CLI/TUI</text>
    <text x="18" y="52" class="rail-title">Private Homebrew Tap (nate/tools) · Reference: Ullr / Yager</text>
    <text x="18" y="74" class="body-text">Sandboxed formula inreplace prevents source drift · Dynamic version injection during brew sandbox</text>
  </g>

  <!-- Rail C: Desktop OTA -->
  <g transform="translate(370, 310)">
    <rect width="490" height="90" rx="6" fill="{p['card_bg']}" stroke="{p['card_border']}" stroke-width="1.2"/>
    <text x="18" y="26" class="rail-badge" fill="{p['green']}">RAIL C · DESKTOP APP CLIENT OTA</text>
    <text x="18" y="52" class="rail-title">Signed Bundles + Minisign Ed25519 · Reference: Idunn</text>
    <text x="18" y="74" class="body-text">Pre-built binary signed with repo key · Manifest (latest.json) verified by in-app background updater</text>
  </g>
</svg>'''
    with open(os.path.join(DIAGRAMS_DIR, f"diagram2-three-rails-{edition}.svg"), "w") as f:
        f.write(svg)

def generate_diagram_3(edition):
    """Diagram 3: The Parity Triangle (Tag == Values == Digest)"""
    p = PALETTES[edition]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 380" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 20px; font-weight: 600; fill: {p['text_primary']}; }}
      .subtitle {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['text_secondary']}; letter-spacing: 0.12em; }}
      .node-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 600; fill: {p['text_primary']}; }}
      .body-text {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; fill: {p['text_secondary']}; }}
      .code-text {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['cyan']}; }}
      .badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.08em; }}
      .gate-title {{ font-family: 'IBM Plex Mono', monospace; font-size: 13px; font-weight: 600; fill: {p['accent']}; letter-spacing: 0.1em; }}
    </style>
  </defs>

  <rect width="100%" height="100%" fill="{p['bg']}" rx="8"/>

  <!-- Header -->
  <text x="40" y="45" class="title">The Release Parity Triangle</text>
  <text x="40" y="68" class="subtitle">PROVING ZERO DRIFT BEFORE PROMOTION CAN PROCEED</text>

  <!-- Triangle Layout -->
  <!-- Top Node: Git Tag -->
  <g transform="translate(330, 95)">
    <rect width="240" height="90" rx="6" fill="{p['card_bg']}" stroke="{p['gold']}" stroke-width="1.5"/>
    <text x="16" y="24" class="badge" fill="{p['gold']}">VERTEX 1 · HUMAN SEMVER</text>
    <text x="16" y="48" class="node-title">Annotated Git Tag</text>
    <text x="16" y="70" class="code-text">refs/tags/v1.0.3</text>
  </g>

  <!-- Bottom Left: Helm Manifests -->
  <g transform="translate(80, 240)">
    <rect width="260" height="110" rx="6" fill="{p['card_bg']}" stroke="{p['cyan']}" stroke-width="1.5"/>
    <text x="16" y="24" class="badge" fill="{p['cyan']}">VERTEX 2 · REPO MANIFESTS</text>
    <text x="16" y="48" class="node-title">Chart &amp; Values Metadata</text>
    <text x="16" y="70" class="code-text">Chart.yaml: appVersion: 1.0.3</text>
    <text x="16" y="90" class="code-text">values.yaml: image.digest: sha256:...</text>
  </g>

  <!-- Bottom Right: Registry Digest -->
  <g transform="translate(560, 240)">
    <rect width="260" height="110" rx="6" fill="{p['card_bg']}" stroke="{p['green']}" stroke-width="1.5"/>
    <text x="16" y="24" class="badge" fill="{p['green']}">VERTEX 3 · OCI REGISTRY</text>
    <text x="16" y="48" class="node-title">Immutable Registry Digest</text>
    <text x="16" y="70" class="code-text">harbor: :b42 == :sha-9e8a...</text>
    <text x="16" y="90" class="code-text">retagged to: :v1.0.3 @ digest</text>
  </g>

  <!-- Connecting Lines -->
  <line x1="370" y1="185" x2="250" y2="240" stroke="{p['arrow']}" stroke-width="1.5" stroke-dasharray="4"/>
  <line x1="530" y1="185" x2="650" y2="240" stroke="{p['arrow']}" stroke-width="1.5" stroke-dasharray="4"/>
  <line x1="340" y1="295" x2="560" y2="295" stroke="{p['arrow']}" stroke-width="1.5" stroke-dasharray="4"/>

  <!-- Center Parity Gate -->
  <g transform="translate(365, 220)">
    <rect width="170" height="80" rx="6" fill="{p['card_bg']}" stroke="{p['accent']}" stroke-width="1.8"/>
    <text x="18" y="28" class="gate-title">PARITY GATE</text>
    <text x="18" y="48" class="body-text">check-release-tag.sh</text>
    <text x="18" y="66" class="code-text" style="font-size: 10px;">drift == 0 ? PASS : FAIL</text>
  </g>
</svg>'''
    with open(os.path.join(DIAGRAMS_DIR, f"diagram3-parity-triangle-{edition}.svg"), "w") as f:
        f.write(svg)

def generate_diagram_4(edition):
    """Diagram 4: Security Blast Radius (App Deploys vs Identity Elevation)"""
    p = PALETTES[edition]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 380" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 20px; font-weight: 600; fill: {p['text_primary']}; }}
      .subtitle {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['text_secondary']}; letter-spacing: 0.12em; }}
      .tier-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 600; fill: {p['text_primary']}; }}
      .body-text {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; fill: {p['text_secondary']}; }}
      .code-text {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; fill: {p['cyan']}; }}
      .badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; font-weight: 600; letter-spacing: 0.08em; }}
    </style>
  </defs>

  <rect width="100%" height="100%" fill="{p['bg']}" rx="8"/>

  <!-- Header -->
  <text x="40" y="45" class="title">Security Blast Radius: Separation of Authority</text>
  <text x="40" y="68" class="subtitle">SPLITTING ROUTINE APPLICATION DEPLOYS FROM IDENTITY-PLANE ELEVATION</text>

  <!-- Low Blast Radius: App Deploys -->
  <g transform="translate(40, 105)">
    <rect width="390" height="235" rx="6" fill="{p['card_bg']}" stroke="{p['green']}" stroke-width="1.4"/>
    <rect x="0" y="0" width="390" height="32" rx="6" fill="{p['green']}" opacity="0.15"/>
    <text x="18" y="22" class="badge" fill="{p['green']}">SURFACE 1 · LOW BLAST RADIUS (AUTONOMOUS)</text>
    <text x="18" y="58" class="tier-title">Application Deployments</text>
    <text x="18" y="80" class="subtitle">CONTAINER IMAGES · HELM VALUES · APP CODE</text>
    <text x="18" y="112" class="body-text">• Merge to main is approval to deploy.</text>
    <text x="18" y="132" class="body-text">• Argo CD pulls and reconciles immutable digests.</text>
    <text x="18" y="152" class="body-text">• Non-elevation event: no privileged secrets required.</text>
    <text x="18" y="172" class="body-text">• Rollback: point Argo back to prior tag/digest.</text>
    <line x1="18" y1="192" x2="372" y2="192" stroke="{p['card_border']}" stroke-width="1"/>
    <text x="18" y="215" class="code-text">Auth: CI Robot Token (Push/Pull only)</text>
  </g>

  <!-- High Blast Radius: Identity & Infra Mutations -->
  <g transform="translate(470, 105)">
    <rect width="390" height="235" rx="6" fill="{p['card_bg']}" stroke="{p['accent']}" stroke-width="1.6"/>
    <rect x="0" y="0" width="390" height="32" rx="6" fill="{p['accent']}" opacity="0.2"/>
    <text x="18" y="22" class="badge" fill="{p['accent']}">SURFACE 2 · HIGH BLAST RADIUS (ELEVATION)</text>
    <text x="18" y="58" class="tier-title">Identity &amp; Control Plane Mutations</text>
    <text x="18" y="80" class="subtitle">KEYCLOAK · OPENBAO · HARBOR RULES · OIDC</text>
    <text x="18" y="112" class="body-text">• Pull Request runs read-only `terraform plan`.</text>
    <text x="18" y="132" class="body-text">• `apply` on merge is an explicit ELEVATION event.</text>
    <text x="18" y="152" class="body-text">• Gated by Valkyrie MFAA single-use approval.</text>
    <text x="18" y="172" class="body-text">• Approval is cryptographically bound to sha256(plan).</text>
    <line x1="18" y1="192" x2="372" y2="192" stroke="{p['card_border']}" stroke-width="1"/>
    <text x="18" y="215" class="code-text" style="fill: {p['accent']};">Auth: OpenBao AppRole + Action-Hash Gate</text>
  </g>
</svg>'''
    with open(os.path.join(DIAGRAMS_DIR, f"diagram4-blast-radius-{edition}.svg"), "w") as f:
        f.write(svg)

for edition in ("dark", "print"):
    generate_diagram_1(edition)
    generate_diagram_2(edition)
    generate_diagram_3(edition)
    generate_diagram_4(edition)
    print(f"Generated 4 {edition} diagrams in {DIAGRAMS_DIR}")
