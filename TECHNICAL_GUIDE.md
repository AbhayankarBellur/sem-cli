# sem-cli: Detailed Technical Implementation Guide

This guide provides an in-depth technical analysis of **`sem-cli` / EngiScope (Software Engineering Metrics & Intelligence CLI)** (published on PyPI as [`engiscope`](https://pypi.org/project/engiscope/), CLI entrypoint: `sem`). It explains the design principles, internal abstractions, mathematical algorithms, AST parsers, database schema, and operational mechanics for every command in the suite.

---

## 1. System Architecture & Component Interaction

`sem-cli` is engineered with strict decoupling between CLI interaction, deterministic metric calculation, repository mining, local SQLite persistence, and optional AI reasoning.

```
                           ┌──────────────────────────────┐
                           │   Terminal UI & CLI Layer    │
                           │     (Typer, Rich, TUI)       │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │  Orchestration Service Layer │
                           │    (analysis_service.py)     │
                           └──────────────┬───────────────┘
                                          │
         ┌──────────────────┬─────────────┴────────────┬──────────────────┐
         ▼                  ▼                          ▼                  ▼
┌──────────────────┐ ┌───────────────┐      ┌──────────────────┐ ┌────────────────┐
│ Ingestion Engine │ │ Static Engine │      │ History Engine   │ │ SQLite DB      │
│ - url_parser     │ │ - AST / Radon │      │ - git_client     │ │ - Repositories │
│ - clone_manager  │ │ - Lizard      │      │ - numstat churn  │ │ - Runs/Metrics │
│ - resolver       │ │ - structural  │      │ - Gini index     │ │ - Findings     │
│ - file_inventory │ │ - security    │      │ - contributors   │ │ - Comparisons  │
└──────────────────┘ └───────────────┘      └──────────────────┘ └────────────────┘
                            │                          │
                            └─────────────┬────────────┘
                                          ▼
                           ┌──────────────────────────────┐
                           │   Analytics & Risk Engine    │
                           │  - Hotspots: H_f = C_f * N_f │
                           │  - Descriptive Stats & IQR   │
                           │  - Pearson / Spearman Corrs  │
                           └──────────────┬───────────────┘
                                          │
                                          ▼ (Optional)
                           ┌──────────────────────────────┐
                           │   Gemini 3.8 Flash SDK       │
                           │   (Evidence-grounded review) │
                           └──────────────────────────────┘
```

### Architectural Separation Rules
1. **Controllers contain no business logic**: Typer commands merely validate CLI arguments and invoke orchestration services.
2. **Metrics before AI**: All measurements originate from deterministic algorithms. The system never depends on an API key or network connection to compute metrics.
3. **No full source transmission**: When Gemini is enabled, only an aggregated evidence payload is dispatched. Source code remains on the user's local disk.
4. **Fault isolation**: Failure of an optional analyzer (e.g., Lizard on an unsupported dialect, or Gemini network quota) records a diagnostic error without invalidating completed metrics.

---

## 2. Ingestion & Workspace Lifecycle

### 2.1 URL Parsing & Credential Stripping (`url_parser.py`)
Incoming target identifiers can be local directory paths (`.`, `D:/projects/repo`), SSH addresses (`git@github.com:org/repo.git`), or remote HTTP/HTTPS URLs (`https://github.com/org/repo.git`).

- **Sanitization**: Regular expressions strip inline basic authentication credentials (`https://user:token@github.com/...` $\to$ `https://github.com/...`) before logging or SQLite persistence.
- **Normalization**: Remote endpoints are normalized with a standardized `.git` suffix to guarantee idempotent database lookups.
- **Local Fallback**: Local directory targets resolve to absolute filesystem paths with file scheme representation (`file:///...`).

### 2.2 Safe Subprocess Git Client (`git_client.py`)
All Git commands execute via standard subprocess argument vectors (`shell=False`) rather than interpolated shell strings.
- **Timeout Management**: Long-running clones or log parsing enforce strict configurable deadlines (`clone_timeout_seconds`).
- **Error Redaction**: Standard error streams are intercepted to scrub access tokens (e.g., `ghp_`, `glpat-`) before raising `GitCommandError` or `GitAuthError`.

### 2.3 Revision Resolution (`revision_resolver.py`)
To prevent "moving target" ambiguities (where a mutable branch like `main` or `HEAD` changes during or after analysis), the resolver executes:
```bash
git rev-parse HEAD
```
This binds the analysis run to an immutable **40-character hexadecimal commit SHA**. The exact SHA is recorded alongside tool version metadata.

### 2.4 Disposable Workspace Management (`clone_manager.py`)
When analyzing remote repositories, `CloneManager` creates a temporary directory prefixed with `sem-<run_id>-` inside `~/.sem-cli/workspaces/`.
- **Shallow Cloning**: Bounded history limits (`--depth <N>`) optimize network utilization for multi-gigabyte repositories.
- **Deterministic Cleanup**: An automated context manager (`managed_workspace`) guarantees deletion of the temporary clone upon completion or interruption, handling Windows read-only file locks through `stat.S_IWRITE` overrides.

### 2.5 File Discovery & Test Classification (`file_inventory.py`)
The engine discovers tracked files via `git ls-files` (falling back to directory traversal if outside Git):
- **Language Detection**: Classifies 25+ file extensions into programming languages (Python, TypeScript, JavaScript, Go, Rust, Java, C/C++, etc.).
- **Test Segregation**: Recognizes test suites via directory paths (`tests/`, `__tests__/`, `spec/`) and naming conventions (`test_*.py`, `*.spec.ts`, `*_test.go`).
- **Exclusion Filters**: Ignores lock files (`package-lock.json`, `bun.lock`), virtual environments (`.venv`), compiler caches (`__pycache__`), and vendor directories.

---

## 3. Metrics Engine & Mathematical Formulations

### 3.1 Product & Size Metrics (`product.py`)
- **Physical LOC ($LOC$)**: Raw line count including blank lines and comments.
- **Source Lines of Code ($SLOC$)**: Lines containing actual executable statements or declarations. Single-line and multi-line comments (`/* ... */`, `""" ... """`, `#`, `//`) and whitespace are stripped.
- **Comment Density ($CD$)**:
  $$CD = \frac{\text{Comment Lines}}{\max(\text{SLOC}, 1)}$$
- **Test-to-Source Ratio ($TSR$)**:
  $$TSR = \frac{\text{Test SLOC}}{\max(\text{Production SLOC}, 1)}$$

### 3.2 Complexity & Maintainability Metrics (`complexity.py`)

#### Cyclomatic Complexity ($CC$)
Estimates the number of linearly independent control-flow paths through McCabe's formula:
$$CC = E - N + 2P$$
Where $E$ is edges, $N$ is nodes, and $P$ is connected components.
- In Python, `radon.complexity` visits the AST, incrementing complexity for `if`, `elif`, `for`, `while`, `except`, `with`, `assert`, and boolean comprehension operations.
- In polyglot files (JS, TS, C++, Java, Go), `lizard` evaluates function-level branching.

#### Halstead Software Science Metrics
Based on token counts:
- $\eta_1$: Distinct operators
- $\eta_2$: Distinct operands
- $N_1$: Total operators
- $N_2$: Total operands
- **Vocabulary**: $\eta = \eta_1 + \eta_2$
- **Length**: $N = N_1 + N_2$
- **Volume ($V$)**:
  $$V = N \times \log_2(\eta)$$
- **Difficulty ($D$)**:
  $$D = \left(\frac{\eta_1}{2}\right) \times \left(\frac{N_2}{\max(\eta_2, 1)}\right)$$
- **Effort ($E$)**:
  $$E = D \times V$$
- **Bugs Delivered Estimate ($B$)**:
  $$B = \frac{V}{3000}$$

#### Maintainability Index ($MI$)
Computed using the SEI/Radon variant normalized to a $[0, 100]$ scale:
$$\text{Raw } MI = 171 - 5.2 \ln(V) - 0.23 CC - 16.2 \ln(LOC) + 50 \sin(\sqrt{2.4 \times C})$$
$$\text{Normalized } MI = \max\left(0.0, \min\left(100.0, \frac{\text{Raw } MI \times 100}{171}\right)\right)$$
Where $V$ is Halstead volume, $CC$ is function-average cyclomatic complexity, and $C$ is comment percentage.

#### Complexity Distribution Bands
Functions are categorized into 4 risk tiers:
- **Low**: $CC \in [1, 5]$
- **Moderate**: $CC \in [6, 10]$
- **High**: $CC \in [11, 20]$
- **Very High**: $CC \ge 21$

---

### 3.3 Structural & Object-Oriented Metrics (`structural.py`)
Computes the Chidamber & Kemerer (CK) object-oriented metric suite via AST analysis:

1. **Weighted Methods per Class ($WMC$)**: Sum of cyclomatic complexities across all member methods in a class:
   $$WMC = \sum_{i=1}^{M} CC(m_i)$$
2. **Depth of Inheritance Tree ($DIT$)**: Maximum length of the inheritance hierarchy from the base object to the declared class.
3. **Number of Children ($NOC$)**: Count of immediate subclasses derived from the class within the analyzed codebase.
4. **Coupling Between Objects ($CBO$)**: Number of distinct external classes referenced through type annotations, inheritance, or instantiations.
5. **Response for a Class ($RFC$)**: Number of member methods plus distinct external methods called by the class:
   $$RFC = |M| + |R|$$
6. **Lack of Cohesion in Methods ($LCOM4$)**: Formulated as the number of connected components in an undirected graph where nodes are methods and edges represent shared instance variable (`self.attr`) accesses:
   $$LCOM4 = \text{ConnectedComponents}(G)$$
   - $LCOM4 = 1$: High cohesion (single responsibility).
   - $LCOM4 > 1$: Low cohesion (candidate for decomposition into multiple classes).

#### Architectural Coupling & Cycle Detection
- **Fan-Out**: Count of distinct internal modules imported by a file.
- **Fan-In**: Count of external modules within the project that import the file.
- **Circular Dependency Detection**: Evaluates the module dependency graph using depth-first search (DFS) with recursion call stacks to detect elementary dependency cycles (e.g., $A \to B \to C \to A$).

---

## 4. Git History & Evolution Mining

### 4.1 Commit & Line Churn Extraction (`history_service.py`)
Mines repository commit streams via:
```bash
git log -n <depth> --format="---SEM_COMMIT---%H|%P|%an|%ae|%cI|%s" --numstat
```
- **Code Churn**:
  $$\text{Churn}_f = \text{Lines Added}_f + \text{Lines Deleted}_f$$
- **Change Frequency ($N_f$)**: Number of distinct historical commits that modified file $f$.

### 4.2 Contributor Identity Normalization
Eliminates duplicate contributor identities by normalizing whitespace and casing on email address (falling back to author name when email is omitted).

### 4.3 Change Concentration Gini Coefficient ($G$)
Measures whether development effort is evenly distributed or concentrated in a fragile subset of files:
$$G = \frac{\sum_{i=1}^{n} (2i - n - 1) x_i}{n \sum_{i=1}^{n} x_i}$$
Where $x_i$ represents file churn values sorted in ascending order.
- $G = 0.0$: Perfectly uniform code modifications.
- $G \to 1.0$: Severe change concentration (Pareto principle: majority of changes target small group of files).

---

## 5. Quality, Security & Dependency Auditor

### 5.1 Code Smell Detection (`quality.py`)
- **Long Method**: Functions exceeding 50 SLOC or $CC > 15$.
- **God Class**: Classes with $WMC > 30$ or method count $> 15$.
- **Deep Nesting**: Block nesting depth $> 4$ (`if`, `for`, `while`, `try`).
- **Long Parameter List**: Signatures with $> 5$ positional/keyword arguments.

### 5.2 Secret Detection & Automatic Redaction (`security_analyzer.py`)
- **Pattern Matching**: Detects AWS Access Keys (`AKIA[0-9A-Z]{16}`), RSA/EC Private Key headers, JWT tokens (`eyJ...`), and generic credential assignments (`api_key = "..."`).
- **Shannon Entropy Verification**:
  $$H(X) = -\sum_{i=1}^{k} P(x_i) \log_2 P(x_i)$$
  Identifies randomly generated tokens in source code.
- **Automatic Redaction**: Masking replaces sensitive bodies (`AKIA************PLE`) to prevent leaks into terminal displays, SQLite databases, or AI prompts.

### 5.3 Static Security Vulnerability Rules
- `SEC-EVAL-EXEC`: Dynamic execution via `eval()` or `exec()`.
- `SEC-SHELL-TRUE`: Unsanitized command execution via `subprocess.run(shell=True)`.
- `SEC-SQL-FORMATTING`: SQL queries constructed using f-strings or format interpolation instead of parameterized queries.
- `SEC-INSECURE-DESERIALIZATION`: Unsafe object parsing via `pickle.loads()`.
- `SEC-INSECURE-HASH`: Legacy hashing (`md5`, `sha1`) utilized in security-sensitive contexts.

### 5.4 Dependency Manifest Parsing (`dependency_analyzer.py`)
Parses `requirements.txt`, `pyproject.toml`, and `package.json`:
- Builds dependency inventories (package name, version specification, ecosystem).
- Flags unpinned packages (`*`, `latest`, missing constraints) as supply chain risks.

---

## 6. Analytics & Decision Support Engine

### 6.1 Descriptive Statistics & Outliers (`descriptive.py`, `outliers.py`)
For any metric distribution vector $X$:
- Mean ($\bar{x}$), Median ($\tilde{x}$), Variance ($s^2$), Standard Deviation ($s$).
- Quartiles: $Q_1$ (25th percentile), $Q_3$ (75th percentile), and Interquartile Range ($IQR = Q_3 - Q_1$).
- Skewness:
  $$\text{Skew} = \frac{\frac{1}{n} \sum_{i=1}^{n} (x_i - \bar{x})^3}{s^3}$$
- **Tukey's Outlier Fencing**: Identifies modules exceeding:
  $$\text{Upper Fence} = Q_3 + 1.5 \times IQR$$
  $$\text{Extreme Fence} = Q_3 + 3.0 \times IQR$$

### 6.2 Empirical Correlation Analysis (`correlation.py`)
Computes both parametric and non-parametric associations:
- **Pearson $r$**: Linear relationship between metrics.
- **Spearman $\rho$**: Monotonic rank correlation.
- **P-Value & Sample Size**: Tests whether observed correlations are statistically significant ($p < 0.05$).
- **Non-Causality Principle**: The system explicitly labels results as empirical correlations, guarding against misinterpreting correlation as causation.

---

### 6.3 Deterministic Hotspot Prioritization Model (`hotspots.py`)
To isolate refactoring targets without speculative defect predictions, `sem-cli` calculates:

$$H_f = C_f \times N_f$$

Where:
- $C_f$: Min-max normalized maximum cyclomatic complexity of file $f$.
- $N_f$: Min-max normalized historical change frequency of file $f$.

#### Normalization Formulation
$$x'_f = \frac{x_f - x_{\min}}{\max(x_{\max} - x_{\min}, \epsilon)}$$
If $x_{\max} = x_{\min}$ (uniform metric distribution), $x'_f$ defaults to $0.5$ to prevent division by zero.

#### Priority Tiers
- **Critical**: $H_f \ge 0.50$ (high complexity and frequent churn)
- **High**: $H_f \in [0.25, 0.49]$
- **Medium**: $H_f \in [0.10, 0.24]$
- **Low**: $H_f < 0.10$

---

### 6.4 Deterministic Risk Assessment Model (`risk.py`)
Calculates an overall codebase risk score $[0.0, 1.0]$:

$$\text{Risk} = 0.35 \cdot H_{\text{top5}} + 0.30 \cdot S_{\text{sec}} + 0.20 \cdot \left(\frac{100 - MI_{\text{avg}}}{100}\right) + 0.15 \cdot \min\left(1.0, \frac{\text{SmellRatio}}{5.0}\right)$$

Where:
- $H_{\text{top5}}$: Mean hotspot score of the top 5 hotspots.
- $S_{\text{sec}}$: Security penalty: $\min(1.0, 0.5 \times \text{Critical} + 0.2 \times \text{High})$.
- $MI_{\text{avg}}$: Average repository Maintainability Index.
- $\text{SmellRatio}$: Code smell count per file.

Risk Levels:
- **Low**: $< 0.25$
- **Moderate**: $0.25 - 0.44$
- **High**: $0.45 - 0.69$
- **Critical**: $\ge 0.70$

---

## 7. SQLite Persistence & Schema Architecture

All records persist in `~/.sem-cli/sem_data.db` (WAL journal mode, foreign key enforcement enabled).

```sql
PRAGMA foreign_keys = ON;

-- Tracked Git repositories
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_url TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Every analysis execution
CREATE TABLE analysis_runs (
    id TEXT PRIMARY KEY,
    repository_id INTEGER NOT NULL,
    requested_ref TEXT,
    commit_sha TEXT,
    status TEXT NOT NULL, -- queued, running, completed, partial, failed
    profile TEXT NOT NULL, -- quick, full
    started_at TEXT NOT NULL,
    completed_at TEXT,
    tool_version TEXT NOT NULL,
    error_code TEXT,
    error_summary TEXT,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Normalized metric storage
CREATE TABLE metric_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL,
    scope_type TEXT NOT NULL, -- repository, file, class, function
    scope_key TEXT NOT NULL,
    status TEXT NOT NULL,    -- measured, unsupported, not_applicable, error
    analyzer TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    explanation TEXT,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

-- Rule findings
CREATE TABLE findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,  -- critical, high, medium, low, info
    confidence TEXT,
    message TEXT NOT NULL,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    evidence TEXT,
    tool_name TEXT NOT NULL,
    tool_version TEXT,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

-- Historical commits
CREATE TABLE commits (
    repository_id INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    author_identity TEXT,
    author_timestamp TEXT,
    committer_timestamp TEXT,
    subject TEXT,
    PRIMARY KEY (repository_id, commit_sha),
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- File-level historical changes
CREATE TABLE commit_changes (
    repository_id INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    file_path TEXT NOT NULL,
    change_type TEXT,
    lines_added INTEGER,
    lines_deleted INTEGER,
    PRIMARY KEY (repository_id, commit_sha, file_path),
    FOREIGN KEY (repository_id, commit_sha) REFERENCES commits(repository_id, commit_sha) ON DELETE CASCADE
);
```

### Snapshot Comparison Algorithm
When comparing two runs (`run_id_a` and `run_id_b`):
1. Loads metric dictionaries keyed by `scope_type:scope_key:name`.
2. Computes absolute difference: $\Delta = V_b - V_a$.
3. Computes relative percentage change:
   $$\% \Delta = \left(\frac{V_b - V_a}{V_a}\right) \times 100$$
4. Identifies new versus resolved findings by diffing `(rule_id, file_path)` tuples.

---

## 8. Gemini 3.8 Flash AI Integration

`sem-cli` integrates with the official Google GenAI SDK (`google.genai`) targeting model `gemini-3.8-flash`.

### Evidence Payload Structure
Rather than streaming entire file trees, `sem-cli` packages computed facts:
```json
{
  "repository_name": "student-ci-manager",
  "commit_sha": "a712cbc8...",
  "business_context": "Student CI/CD build management platform",
  "metrics_summary": {
    "total_sloc": 16015,
    "function_count": 366,
    "high_complexity_function_count": 9,
    "avg_maintainability_index": 72.4
  },
  "top_hotspots": [
    {
      "file": "src/pages/StudentDetail.tsx",
      "hotspot_score": 0.200,
      "complexity": 61.0,
      "change_frequency": 2,
      "priority": "MEDIUM",
      "reasons": ["High complexity (CC=61.0)", "Function 'StudentDetail' is too long (320 NLOC)"]
    }
  ],
  "top_findings": [
    {
      "rule_id": "SMELL-LONG-METHOD",
      "severity": "medium",
      "file": "src/pages/StudentDetail.tsx",
      "line": 15
    }
  ],
  "risk_assessment": {
    "overall_score": 0.32,
    "level": "Moderate"
  }
}
```

### Prompt Guardrails
- **No Hallucinations**: System instructions forbid inventing metrics or asserting vulnerabilities not present in the evidence payload.
- **Evidence References**: Recommendations must explicitly cite the affected file and metric value.
- **JSON Schema Validation**: Responses are constrained to structured JSON (`response_mime_type="application/json"`).

---

## 9. Command Reference & Internal Execution Flow

### 9.1 `sem` (Interactive Home Screen)
- **Role**: Launches the interactive TUI workspace.
- **Under the Hood**:
  1. Inspects the current working directory for `.git`.
  2. Resolves HEAD commit SHA, branch name, and tracked file count.
  3. Displays Rich Unicode banner with quick menu actions (1–8).
  4. Dispatches the selected action to the corresponding command handler.

### 9.2 `sem doctor`
- **Role**: System diagnostics and readiness verification.
- **Under the Hood**:
  1. Verifies Git executable via `shutil.which("git")` and extracts version string (`git --version`).
  2. Verifies Python runtime compatibility (Python 3.12+).
  3. Tests SQLite database read/write access at `~/.sem-cli/sem_data.db`.
  4. Tests imports for `radon` and `lizard`.
  5. Checks whether `GEMINI_API_KEY` is set and verifies model configuration (`gemini-3.8-flash`).

### 9.3 `sem init`
- **Role**: Generates default user configuration file.
- **Under the Hood**:
  Creates `~/.sem-cli/config.toml` pre-populated with analysis thresholds, repository retention policies, and security toggles.

### 9.4 `sem analyze <TARGET>`
- **Role**: Runs the full ingestion, mining, analysis, and persistence pipeline.
- **Options**:
  - `--ref <REF>`: Target branch, tag, or commit SHA.
  - `--history-depth <N>`: Maximum commits to mine.
  - `--profile <quick|full>`: Quick runs core metrics; full executes security and CK suite.
  - `--no-ai`: Disables Gemini AI analysis.
  - `--business-context <TEXT>`: Optional business description for AI interpretation.
- **Under the Hood**:
  1. Validates and normalizes target (`url_parser.py`).
  2. Creates an `analysis_runs` record in SQLite (`status='running'`).
  3. Clones repository to `~/.sem-cli/workspaces/sem-<run_id>-` if remote (`clone_manager.py`).
  4. Resolves exact commit SHA (`revision_resolver.py`).
  5. Discovers source files, filters generated code, and classifies test suites (`file_inventory.py`).
  6. Mines Git log with `--numstat` to calculate churn and Gini coefficient (`history_service.py`).
  7. Runs static analyzers: Radon, Lizard, CK structural rules, secrets scanner, dependency scanner (`registry.py`).
  8. Ranks hotspots via $H_f = C_f \times N_f$ (`hotspots.py`).
  9. Calculates descriptive stats, outliers, and correlations (`descriptive.py`, `correlation.py`).
  10. Evaluates overall risk score (`risk.py`).
  11. If AI is enabled, packages evidence and invokes Gemini 3.8 Flash (`ai_service.py`).
  12. Persists metrics, findings, commits, and dependencies inside an ACID SQLite transaction.
  13. Deletes temporary workspace directory unless `--retain-clone` is configured.
  14. Renders Unicode results screen and returns exit code `0` (or `7` on partial warnings).

### 9.5 `sem metrics <TARGET>`
- **Role**: Displays the software metrics catalogue.
- **Under the Hood**:
  Queries SQLite for the latest completed run matching the normalized target URL. If no previous run exists, triggers an on-demand analysis. Displays formatted metrics grouped by Product, Complexity, and Structural categories.

### 9.6 `sem hotspots <TARGET>`
- **Role**: Ranks modules combining high complexity and churn.
- **Options**: `--limit <N>` (default: 15).
- **Under the Hood**:
  Calculates normalized scores $C_f$ and $N_f$, sorts descending by $H_f = C_f \times N_f$, and renders priority badges (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) with supporting evidence.

### 9.7 `sem history <TARGET>`
- **Role**: Mines repository history, commit volume, and contributors.
- **Options**: `--depth <N>` (default: 100).
- **Under the Hood**:
  Parses author identities, dates, additions, and deletions. Computes total churn and Gini inequality index. Displays normalized contributor activity rankings.

### 9.8 `sem security <TARGET>`
- **Role**: Audits static security risks, hardcoded credentials, and dependency risks.
- **Under the Hood**:
  Executes regex and Shannon entropy secret scans, AST security checks (`eval`, `shell=True`, SQL injection), and dependency manifest unpinned package detection.

### 9.9 `sem stats <TARGET>`
- **Role**: Computes distribution statistics and empirical correlations.
- **Under the Hood**:
  Generates quartile tables for $CC$, $SLOC$, and Churn distributions. Runs SciPy Pearson and Spearman correlation analysis between metrics, reporting sample size $N$, $p$-values, and non-causal interpretations.

### 9.10 `sem compare <TARGET>`
- **Role**: Evaluates metric deltas between revisions or stored snapshots.
- **Options**:
  - `--from <REF_A> --to <REF_B>`: Compares two Git revisions.
  - `--run-a <ID_1> --run-b <ID_2>`: Compares two stored run IDs.
- **Under the Hood**:
  Computes metric deltas ($V_b - V_a$, $\% \Delta$) and lists newly introduced versus resolved findings.

### 9.11 `sem ask <TARGET> "<QUESTION>"`
- **Role**: Answers architectural and refactoring questions via Gemini 3.8 Flash.
- **Options**: `--mode <engineering_review|architecture_review|risk_review|business_impact>`.
- **Under the Hood**:
  Loads stored metrics, findings, and hotspots from SQLite, constructs the sanitized evidence payload, invokes Gemini 3.8 Flash, and displays structured risks, recommendations, and evidence references.

### 9.12 `sem report <TARGET>` & `sem export <TARGET>`
- **Role**: Serializes analysis results into documentation or machine-readable exports.
- **Options**:
  - `--format <markdown|json|csv|terminal>`
  - `--output <PATH>`
- **Under the Hood**:
  - `markdown`: Generates an engineering report with tables and risk breakdown.
  - `json`: Emits complete structured JSON containing all metric rows, findings, and hotspots for CI/CD gates.
  - `csv`: Outputs tabular metric rows with scope keys and values.

### 9.13 `sem runs`
- **Role**: Lists historical analysis snapshots.
- **Options**: `--limit <N>` (default: 20).
- **Under the Hood**:
  Queries the `analysis_runs` SQLite table joined with `repositories`, displaying run IDs, commit SHAs, status, and execution timestamps.

---

## 10. Exit Codes

`sem-cli` returns POSIX-compliant exit codes for automated build pipelines:

| Exit Code | Constant | Meaning |
|---|---|---|
| `0` | `EXIT_SUCCESS` | Analysis or command completed successfully. |
| `1` | `EXIT_INTERNAL_ERROR` | Unhandled runtime exception. |
| `2` | `EXIT_INVALID_ARGS` | Invalid CLI arguments, flags, or missing options. |
| `3` | `EXIT_GIT_FAILURE` | Repository clone, checkout, or ref resolution failed. |
| `4` | `EXIT_ANALYSIS_FAILURE` | Core static parsing or metrics computation failed. |
| `5` | `EXIT_PERSISTENCE_FAILURE` | SQLite read/write or schema migration failed. |
| `6` | `EXIT_POLICY_BLOCKED` | Security policy blocked execution or missing API key. |
| `7` | `EXIT_PARTIAL_SUCCESS` | Core analysis succeeded, but one or more optional stages encountered warnings. |
