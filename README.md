# sem-cli — Software Engineering Metrics & Intelligence CLI

> **Course:** ISWE402L – Software Metrics  
> **Product:** Software Engineering Metrics Ingestion, Analysis, and Decision Support Platform  
> **Interface:** Terminal-based, Unicode TUI inspired by Claude Code  
> **Provider:** Google Gemini API (optional, offline-first fallback)

---

## 1. Product Overview

`sem-cli` transforms Git repositories into an evidence-grounded software engineering analytics environment directly from your terminal. It measures source code, mines Git history, audits quality and security, calculates empirical distributions and correlations, ranks engineering hotspots, and optionally provides Gemini AI-powered business and architectural insights.

### Core Principles
- **Local-first:** Runs entirely on the user's workstation without requiring cloud databases, Docker, or Redis.
- **Metrics before AI:** Numeric measurements originate from deterministic static analysis and Git mining algorithms. AI is an optional interpretation layer, not a dependency for calculating metrics.
- **Evidence-backed:** Every finding and hotspot links to exact files, line numbers, commits, and formula derivations.
- **Reproducible:** Measurements are pinned to exact 40-character Git commit SHAs and recorded in local SQLite database snapshots.
- **Privacy & Security:** Full source code is never sent to Gemini by default; sensitive tokens and credentials are automatically redacted.

---

## 2. Architecture & Design

```
sem-cli
├── CLI Layer           (Typer, Rich, interactive TUI, Claude Code styling)
├── Services Layer      (Analysis orchestration, history mining, reports, AI)
├── Ingestion Engine    (Git client, clone manager, revision resolver, inventory)
├── Analysis Engine     (Radon, Lizard, AST structural analyzers, secrets & deps)
├── Metrics Catalogue   (Product size, complexity, CK OO suite, process, quality)
├── Analytics Layer     (Descriptive statistics, IQR outliers, correlations, hotspots, risk)
└── Persistence Layer   (SQLite transactional snapshots, runs, comparisons)
```

---

## 3. Complete Software Metrics Catalogue

| Category | Metric | Scope | Unit | Definition & Implementation |
|---|---|---|---|---|
| **Product & Size** | Physical LOC (`loc`) | File, Repo | Lines | Total physical lines in source files |
| | Source Lines (`sloc`) | File, Repo | Lines | Executable and declarative lines excluding blanks & comments |
| | Comment Density (`comment_density`) | File | Ratio | Ratio of comment lines to source lines |
| | File & Function Count | Repo | Count | Recognized files, classes, and callable functions |
| | Test-to-Source Ratio (`test_to_source_ratio`) | Repo | Ratio | Test SLOC divided by production source SLOC |
| **Complexity** | Cyclomatic Complexity (`cyclomatic_complexity`) | Function, File | Count | Linearly independent control-flow paths (Radon / Lizard) |
| | Halstead Volume (`halstead_volume`) | File | Bits | $V = N \times \log_2(\eta)$ derived from operators/operands |
| | Halstead Effort (`halstead_effort`) | File | Effort | $E = D \times V$ |
| | Maintainability Index (`maintainability_index`) | File, Repo | Score | SEI/Radon formula scaled to [0, 100] |
| | Complexity Distribution Bands | Repo | Bands | Low (1-5), Moderate (6-10), High (11-20), Very High (21+) |
| **Structural & CK** | Weighted Methods per Class (`wmc`) | Class, Repo | Count | Sum of method complexities in each class |
| | Depth of Inheritance Tree (`dit`) | Class | Levels | Max inheritance levels from base object |
| | Number of Children (`noc`) | Class | Count | Immediate subclasses defined in repository |
| | Coupling Between Objects (`cbo`) | Class, Repo | Count | External class and type references |
| | Lack of Cohesion (`lcom4`) | Class, Repo | Components | Connected components in method-field access graph |
| | Fan-In & Fan-Out | File | Count | Internal module dependencies and callers |
| | Circular Dependencies (`circular_dependency_count`) | Repo | Cycles | Import cycles detected via graph cycle traversal |
| **Process & Churn** | Commit Frequency & Count | Repo | Commits | Commits analyzed in history window |
| | Contributor Count | Repo | Authors | Distinct authors normalized by email identity |
| | Code Churn (`churn`, `total_churn`) | File, Repo | Lines | Added lines + deleted lines across commits |
| | Change Concentration Gini (`churn_gini_concentration`) | Repo | Gini | Gini inequality index of file churn (0=equal, 1=concentrated) |
| **Quality & Security** | Code Smells (`code_smell_count`) | Repo | Count | Long Method, God Class, Deep Nesting, Long Params |
| | Hardcoded Secrets | File | Findings | AWS keys, Private keys, JWT tokens, high-entropy strings |
| | Security Patterns | File | Findings | Dynamic `eval()`, `shell=True`, SQL injection, weak hashes |
| | Dependency Manifest Risks | Repo | Findings | Unpinned dependencies (`*`, `latest`) in manifests |

---

## 4. Hotspot Prioritization Model

To prioritize technical debt without pretending to predict defects without training data, `sem-cli` computes:

$$H_f = C_f \times N_f$$

Where:
- $C_f$ is min-max normalized maximum cyclomatic complexity for file $f \in [0.0, 1.0]$.
- $N_f$ is min-max normalized historical change frequency for file $f \in [0.0, 1.0]$.
- $H_f$ is a transparent prioritization score highlighting modules that combine high structural complexity with frequent churn.

---

## 5. CLI Command Reference

### Interactive Workspace
```bash
# Launch interactive terminal TUI
sem
```

### Ingestion & Analysis
```bash
# Analyze local repository
sem analyze .

# Analyze remote Git repository URL
sem analyze https://github.com/owner/repository.git

# Analyze specific branch, tag, or commit revision
sem analyze https://github.com/owner/repository.git --ref main

# Limit history depth and select profile
sem analyze . --history-depth 500 --profile full

# Provide optional business context for AI interpretation
sem analyze . --business-context "Payment gateway and billing engine"
```

### Focused Exploration
```bash
# Explore software metrics catalogue
sem metrics .

# Rank complexity and churn hotspots
sem hotspots . --limit 15

# Mine Git history, contributors, and churn concentration
sem history . --depth 200

# Run security and secret audit
sem security .

# Run descriptive statistics and empirical correlations
sem stats .

# Compare two analysis revisions or stored snapshots
sem compare . --from v1.0.0 --to v1.1.0
sem compare --run-a <RUN_ID_1> --run-b <RUN_ID_2>

# Ask Google Gemini evidence-grounded questions
sem ask . "Which modules present the highest maintenance risk and why?"

# Generate and export reports
sem report . --format markdown --output REPORT.md
sem export . --format json --output report.json
sem export . --format csv --output metrics.csv

# List past analysis runs
sem runs

# System diagnostics
sem doctor

# Initialize user configuration
sem init
```

---

## 6. Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unexpected internal error |
| `2` | Invalid command or arguments |
| `3` | Git clone or ref resolution failed |
| `4` | Core analysis failed |
| `5` | Persistence failure |
| `6` | Security or configuration policy blocked execution |
| `7` | Partial analysis (warnings/non-fatal stages recorded) |

---

## 7. Gemini AI Integration & Guardrails

- Configured via environment variable: `export GEMINI_API_KEY="your-api-key"`.
- **Offline by Default:** Complete metrics, hotspots, statistics, and reports operate offline without an API key.
- **Minimized Evidence Payload:** Only structured metric aggregates, hotspot rankings, and findings are sent to Gemini. Full source code is never uploaded by default.
- **Guardrails:** AI is instructed never to invent metrics, never to claim vulnerabilities without supporting evidence, and to label operational implications as hypotheses.
