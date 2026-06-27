import re
from typing import Dict, Any, List, Optional

class TroubleshootingPlaybook:
    def __init__(
        self,
        name: str,
        problem_class: str,
        checklist: List[str],
        hypotheses: List[str],
        recommended_tools: List[str],
        diagnostic_steps: List[str],
        clarifying_questions: List[str]
    ):
        self.name = name
        self.problem_class = problem_class
        self.checklist = checklist
        self.hypotheses = hypotheses
        self.recommended_tools = recommended_tools
        self.diagnostic_steps = diagnostic_steps
        self.clarifying_questions = clarifying_questions

    def format_first_response(self) -> str:
        """Formats the playbook as a structured Markdown response."""
        res = []
        res.append(f"### 📋 IMMEDIATE {self.name.upper()} PLAYBOOK CHECKLIST")
        for item in self.checklist:
            res.append(f"- [ ] {item}")
        
        res.append("\n### 🔍 PRIORITIZED HYPOTHESES")
        for idx, h in enumerate(self.hypotheses, 1):
            res.append(f"{idx}. {h}")
            
        res.append("\n### 🛠️ RECOMMENDED DIAGNOSTIC TOOLS")
        for tool in self.recommended_tools:
            res.append(f"- {tool}")
            
        res.append("\n### 👣 NEXT DIAGNOSTIC STEPS")
        for idx, step in enumerate(self.diagnostic_steps, 1):
            res.append(f"{idx}. {step}")
            
        res.append("\n### ❓ HIGH-VALUE CLARIFYING QUESTIONS")
        for q in self.clarifying_questions:
            res.append(f"- {q}")
            
        return "\n".join(res)

# Define all playbooks
PLAYBOOKS = {
    "performance": TroubleshootingPlaybook(
        name="Performance Investigation",
        problem_class="performance",
        checklist=[
            "Reproduce and measure the slowness under normal conditions.",
            "Identify where latency occurs (frontend, backend, DB, network, external API, build/test pipeline).",
            "Use profiling tools (e.g. cProfile, py-spy).",
            "Use monitoring and observability data to inspect resource limits.",
            "Inspect logs, traces, and metrics to find response latency trends.",
            "Check database query performance and execution plans.",
            "Check for N+1 queries, missing indexes, lock contention, high rows scanned, and slow joins.",
            "Check CPU, memory, disk I/O, and connection pool saturation.",
            "Compare current behavior against a known baseline.",
            "Isolate regressions by recent code/config/infrastructure changes."
        ],
        hypotheses=[
            "Resource bottleneck (CPU, RAM, or Disk I/O saturation).",
            "Inefficient database queries (missing index, slow joins, lock contention).",
            "Blocked synchronous executions or thread pool starvation.",
            "Latency in external network calls or third-party APIs."
        ],
        recommended_tools=[
            "Profilers: cProfile, py-spy, line_profiler",
            "System: top, htop, iostat, vmstat",
            "Database: EXPLAIN ANALYZE, pg_stat_statements, slow query logs",
            "Observability: OpenTelemetry, Prometheus, Grafana"
        ],
        diagnostic_steps=[
            "Establish a measurable baseline latency.",
            "Isolate the code section causing slowness into a repeatable benchmark.",
            "Run a profiler on the benchmarks to pinpoint functions holding the CPU.",
            "Examine query execution plans (EXPLAIN) for any database operations invoked."
        ],
        clarifying_questions=[
            "Where is the slowness observed: UI, API, DB, worker, build, or tests?",
            "Is this new or has it always been slow?",
            "Is it reproducible locally, staging, or production only?",
            "Are there metrics, traces, logs, or profiler outputs available?",
            "Are specific endpoints, queries, or jobs involved?",
            "Has anything changed recently (deployment, schema, traffic, config)?"
        ]
    ),
    "crashes": TroubleshootingPlaybook(
        name="Crash Investigation",
        problem_class="crashes",
        checklist=[
            "Capture the full error stack trace.",
            "Extract relevant error messages and exception classes.",
            "Identify the file, function, and line number where the crash occurred.",
            "Inspect local variables or state at the time of the crash (if core dump is available).",
            "Check system logs, event viewers, or central error reporting tools (e.g. Sentry).",
            "Check if the environment has sufficient resources (CPU/RAM limit checks to avoid OOM).",
            "Verify dependency health and version compatibility."
        ],
        hypotheses=[
            "Unhandled edge case (NullPointer, NoneType attribute, Division by zero).",
            "Out of Memory (OOM) event causing system process termination.",
            "Connection failure or socket disconnect with external dependencies.",
            "Type mismatch or invalid parameters passed to methods."
        ],
        recommended_tools=[
            "Error track: Sentry, Rollbar, Bugsnag",
            "Debugging: pdb, ipdb, core dump analyzers",
            "Logs: systemd journalctl, docker logs, syslog"
        ],
        diagnostic_steps=[
            "Reproduce the error locally or in a sandbox.",
            "Locate the stack trace and map it to the active codebase branch.",
            "Add detailed local logging immediately preceding the crash frame.",
            "Check resource limits (e.g. Docker / K8s RAM consumption) near the crash timestamp."
        ],
        clarifying_questions=[
            "What is the exact exception message or stack trace?",
            "What action or request triggers the crash?",
            "Is this crash fully deterministic or intermittent?",
            "Has there been a recent dependency upgrade or DB migration?"
        ]
    ),
    "intermittent": TroubleshootingPlaybook(
        name="Intermittent Failure Investigation",
        problem_class="intermittent",
        checklist=[
            "Collect precise timestamps of failures to find temporal correlation.",
            "Isolate network conditions and external dependencies.",
            "Check for concurrency issues, race conditions, and shared mutable state.",
            "Analyze garbage collection or resource cleanup cycles.",
            "Monitor connection pools and rate limit boundaries."
        ],
        hypotheses=[
            "Race conditions or shared state corruption in concurrent tasks.",
            "Transient network drops or DNS resolution timeout.",
            "API rate limit exhaustion or throttling.",
            "Database lock waits or lock timeout."
        ],
        recommended_tools=[
            "Load testing: Locust, k6",
            "Tracing: Jaeger, Zipkin, AWS X-Ray",
            "Network: tcpdump, wireshark"
        ],
        diagnostic_steps=[
            "Correlate timestamps with other background system activity.",
            "Enable retries with exponential backoff on external calls.",
            "Generate artificial load to increase concurrency and expose race conditions."
        ],
        clarifying_questions=[
            "How frequently does the failure occur (e.g., 1 in 100 requests)?",
            "Is the failure correlated with high traffic or cron jobs?",
            "Do concurrent operations run at the time of failure?"
        ]
    ),
    "flaky_tests": TroubleshootingPlaybook(
        name="Flaky Test Investigation",
        problem_class="flaky_tests",
        checklist=[
            "Check for test order dependencies (pollution of shared state/database).",
            "Inspect use of static or global variables or mock leakages.",
            "Verify time-sensitive tests (datetime.now, timezone boundaries).",
            "Identify asynchronous tasks or background worker delays.",
            "Run test repeatedly (e.g. 100 times) to capture frequency of failure."
        ],
        hypotheses=[
            "State leakage between tests (missing teardown cleanups).",
            "Asynchronous race conditions (tests assert before background job completes).",
            "DateTime dependencies (timezone shifts, leap years, midnight runs).",
            "Shared database constraints violation during parallel execution."
        ],
        recommended_tools=[
            "Pytest plugins: pytest-repeat, pytest-randomly, pytest-xdist",
            "Mocking: freezegun, unittest.mock"
        ],
        diagnostic_steps=[
            "Run the specific test in isolation 100 times.",
            "Change execution order to isolate state pollution.",
            "Introduce mock time freezes for any time-reliant assertions."
        ],
        clarifying_questions=[
            "Does the test fail in isolation, or only during suite runs?",
            "Does the test rely on external databases or network sockets?",
            "Does it fail locally, or only on CI runners?"
        ]
    ),
    "database": TroubleshootingPlaybook(
        name="Database Investigation",
        problem_class="database",
        checklist=[
            "Analyze slow query logs and list queries exceeding threshold.",
            "Inspect EXPLAIN plans for table scans, index hits, and join operations.",
            "Check table statistics and auto-vacuum status.",
            "Monitor active connections and check for connection pool saturation.",
            "Verify lock wait timeouts and deadlocks in database engine logs."
        ],
        hypotheses=[
            "Missing indexes on frequently searched or joined columns.",
            "Stale table statistics leading the query optimizer astray.",
            "Connection pool exhaustion on the application side.",
            "Unclosed transactions holding locks and blocking concurrent queries."
        ],
        recommended_tools=[
            "Database: EXPLAIN, pg_stat_statements, pg_hero, pganalyze",
            "CLI: pg_top, mytop, slow query log analyzers"
        ],
        diagnostic_steps=[
            "Run EXPLAIN ANALYZE on slow query statements.",
            "Verify index usage and check for sequential table scans.",
            "Inspect current database active connection count and lock tables."
        ],
        clarifying_questions=[
            "Which database engines, tables, or queries are involved?",
            "Are connections to the database timing out?",
            "Have table schemas or volumes changed recently?"
        ]
    ),
    "memory": TroubleshootingPlaybook(
        name="Memory Leak Investigation",
        problem_class="memory",
        checklist=[
            "Monitor resident set size (RSS) over time under steady state load.",
            "Check for object accumulation in memory (heap analysis).",
            "Verify cleanup of observers, listeners, or caching layers.",
            "Inspect use of global collections or persistent threads.",
            "Analyze garbage collection frequency and execution times."
        ],
        hypotheses=[
            "References held indefinitely in global lists or caches.",
            "Cyclic references blocking GC in non-ref-counted runtimes.",
            "C-extension library memory leak outside the language VM.",
            "Large files read entirely into memory rather than chunked."
        ],
        recommended_tools=[
            "Python: objgraph, tracemalloc, memory_profiler",
            "Profiler: memray, heapy",
            "OS: valgrind, pmap"
        ],
        diagnostic_steps=[
            "Take memory heap snapshots at startup vs under steady-state load.",
            "Filter accumulating object types to locate leak sources.",
            "Profile memory growth during local loop execution."
        ],
        clarifying_questions=[
            "How rapidly does memory usage increase?",
            "Does memory return to baseline after requests cease?",
            "Are custom caches or global variables in use?"
        ]
    ),
    "cpu": TroubleshootingPlaybook(
        name="CPU Spike Investigation",
        problem_class="cpu",
        checklist=[
            "Locate the specific process or thread ID consuming CPU.",
            "Profile CPU utilization to identify hot functions and call graphs.",
            "Check for infinite loops or high-frequency polling.",
            "Monitor serialization/deserialization overhead (JSON, XML).",
            "Check encryption or hashing algorithms execution frequency."
        ],
        hypotheses=[
            "Infinite loops or polling threads without backoff sleeps.",
            "Heavy serialization/deserialization load.",
            "Thread spinning / lock contention in high concurrency.",
            "Expensive regex matching or mathematical computation."
        ],
        recommended_tools=[
            "System: top, htop, mpstat",
            "Profiler: py-spy, cProfile, perf",
            "Visual: Flame graphs"
        ],
        diagnostic_steps=[
            "Record a flame graph of the active process under load.",
            "Check loops in code for safety limits and backoffs.",
            "Optimize computationally expensive string operations or parsing."
        ],
        clarifying_questions=[
            "Is the spike continuous, periodic, or request-driven?",
            "Which process ID is hogging the CPU?",
            "Is the runtime single-threaded or multi-threaded?"
        ]
    ),
    "networking": TroubleshootingPlaybook(
        name="Network & Timeout Investigation",
        problem_class="networking",
        checklist=[
            "Test basic connectivity using ping, traceroute, or curl.",
            "Inspect network routing, DNS resolution times, and packet drops.",
            "Verify client-side and server-side read/write timeout thresholds.",
            "Monitor socket usage and check for socket exhaustion.",
            "Inspect rate limiting policies and API gateway logs."
        ],
        hypotheses=[
            "Misconfigured security groups, firewalls, or routing tables.",
            "DNS lookup failures or high DNS resolution latency.",
            "Too short read timeouts for heavy payload endpoints.",
            "Outgoing socket exhaustion due to unclosed clients."
        ],
        recommended_tools=[
            "DNS: dig, nslookup",
            "Inspect: curl -iv, traceroute, ping",
            "Socket: netstat, ss, tcpdump"
        ],
        diagnostic_steps=[
            "Trace network hops to the target host to locate failures.",
            "Measure DNS resolution speed separately from request latency.",
            "Verify active client connection/socket closure cycles."
        ],
        clarifying_questions=[
            "What is the exact timeout duration and error message?",
            "Does the connection fail immediately or hang first?",
            "Are you targeting a private VPC resource or an external API?"
        ]
    ),
    "build": TroubleshootingPlaybook(
        name="Build & CI Investigation",
        problem_class="build",
        checklist=[
            "Profile step execution times in the build/pipeline log.",
            "Inspect build caching configuration (compiler cache, package cache).",
            "Check docker image size and optimize layer caching.",
            "Verify network download speeds for dependencies.",
            "Monitor resource allocation (CPU, RAM) on build agents/runners."
        ],
        hypotheses=[
            "Missing or unconfigured build runner cache directories.",
            "Downloading dependencies or node_modules fresh on every build.",
            "Unoptimized Docker layers or massive build context copies.",
            "High test runtimes during the verification phase."
        ],
        recommended_tools=[
            "CI: Github Actions / GitLab runner dashboards",
            "Docker: docker buildx --profile, docker history",
            "Analyze: build scan tools"
        ],
        diagnostic_steps=[
            "Inspect compile, package, and test step execution split.",
            "Check runner CPU/Memory allocation limits.",
            "Optimize Dockerfile caching structures."
        ],
        clarifying_questions=[
            "Which build step is consuming the most time?",
            "Are package dependencies cached on the runner?",
            "Are you building containers or running static analysis?"
        ]
    )
}

def find_matching_playbook(raw_input: str) -> Optional[TroubleshootingPlaybook]:
    """Matches developer input to a specific playbook by looking at patterns/keywords."""
    text = raw_input.lower()
    
    # Pre-check: If input explicitly indicates new feature, planning meeting, or general question, bypass playbooks
    if any(kw in text for kw in ["feature", "meeting", "agenda", "roadmap", "planning", "how to", "how do", "what is", "why does", "explain", "difference"]):
        return None
    
    # 1. Flaky Tests
    flaky_test_patterns = [
        r"\bflaky", r"\btest\s+fails?\s+sometimes", r"\bflake\b", r"\btest\s+slowness"
    ]
    if any(re.search(p, text) for p in flaky_test_patterns):
        return PLAYBOOKS["flaky_tests"]

    # 2. Performance / Slowness
    perf_patterns = [
        r"\bslow", r"\bslowness", r"\blag", r"\blagging", r"\bdelay", r"\blatency", 
        r"\bhang", r"\bhangs", r"\bspeed\b", r"\btime\s+out", r"\btimed\s+out", 
        r"\btiming\s+out", r"\btakes?\s+too\s+long\b", r"\btaking\s+too\s+long\b",
        r"\btaking\s+so\s+much\s+time\b"
    ]
    if any(re.search(p, text) for p in perf_patterns):
        return PLAYBOOKS["performance"]

    # 3. Intermittent Failures
    intermittent_patterns = [
        r"\bintermittent", r"\bsometimes\b", r"\brandomly\b", r"\boccasionally\b", r"\btransient"
    ]
    if any(re.search(p, text) for p in intermittent_patterns):
        return PLAYBOOKS["intermittent"]

    # 4. Memory Leaks / Growth
    memory_patterns = [
        r"\bmemory\s+leak", r"\bleak\b", r"\bleaking", r"\boom\b", r"\bout\s+of\s+memory", 
        r"\bheap\b", r"\brss\b", r"\bmemory\s+growth"
    ]
    if any(re.search(p, text) for p in memory_patterns):
        return PLAYBOOKS["memory"]

    # 5. CPU Spikes
    cpu_patterns = [
        r"\bcpu\b", r"\bspike", r"\b100%", r"\bhigh\s+load", r"\bspinning", r"\binfinite\s+loop"
    ]
    if any(re.search(p, text) for p in cpu_patterns):
        return PLAYBOOKS["cpu"]

    # 6. Database Issues
    db_patterns = [
        r"\bdatabase\b", r"\bdb\b", r"\bsql\b", r"\bpostgres", r"\bmysql", r"\bsqlite",
        r"\bquery\b", r"\bqueries\b", r"\block\s+contention", r"\bmissing\s+index", r"\bslow\s+query"
    ]
    if any(re.search(p, text) for p in db_patterns):
        return PLAYBOOKS["database"]

    # 7. Build / CI
    build_patterns = [
        r"\bbuild\b", r"\bci\b", r"\bpipeline", r"\brunner", r"\bdocker\s+build", r"\bcompilation"
    ]
    if any(re.search(p, text) for p in build_patterns):
        return PLAYBOOKS["build"]

    # 8. Networking
    net_patterns = [
        r"\bnetwork", r"\bsocket", r"\bdns\b", r"\bconnection\b", r"\bping\b", r"\bpacket\b"
    ]
    if any(re.search(p, text) for p in net_patterns):
        return PLAYBOOKS["networking"]

    # 9. Crashes / Exceptions
    crash_patterns = [
        r"\bcrash", r"\bcrashed", r"exception", r"\berror\s+log", r"\bstack\s+trace", 
        r"\bsegfault", r"\bsegmentation\b", r"\bunhandled"
    ]
    if any(re.search(p, text) for p in crash_patterns):
        return PLAYBOOKS["crashes"]

    return None
