OBSERVABILITY_TEMPLATES = {
    "fastapi": [
        "Structured JSON Logging: Log incoming request path, method, client IP, and response status code.",
        "Request ID Propagation: Ensure a unique X-Request-ID header is generated and propagated to all downstream HTTP requests.",
        "FastAPI Latency Metrics: Export Prometheus HTTP request duration histograms split by endpoint and method.",
        "FastAPI Error Rate: Track count of 5xx HTTP responses using a Prometheus Counter."
    ],
    "django": [
        "Structured JSON Logging: Configure django.request logging to output request metadata in JSON format.",
        "Django Latency Metrics: Track request-response cycle latency using custom middleware.",
        "Django DB Connections: Monitor active database connection pool sizes and leak warnings."
    ],
    "database": [
        "Database Slow Query Logs: Configure logging for queries exceeding 100ms thresholds.",
        "Query Profiling: Use EXPLAIN ANALYZE on complex SQL queries to identify table scans and indexing gaps.",
        "Connection Pool Metrics: Monitor connection pool queue sizes and wait times."
    ],
    "async": [
        "Event Loop Blockage: Instrument asyncio loop lag monitoring to detect event loop starvation.",
        "ThreadPoolExecutor Tracking: Track worker queue size and task execution times for blocking operations."
    ],
    "default": [
        "Structured JSON Logging: Use python-json-logger to standardize all stdout logs in JSON format.",
        "Latency Tracing: Implement OpenTelemetry SDK for distributed trace context propagation.",
        "SLA/SLI Tracking: Track endpoint p95/p99 execution latency against service level agreements."
    ]
}

def get_observability_suggestions(context: dict) -> list[str]:
    """Generates deterministic observability recommendations based on the stack context.
    
    The context dict can contain:
    - 'languages': list[str] (e.g. ['Python'])
    - 'dependencies': list[str] (e.g. ['fastapi', 'sqlalchemy'])
    - 'raw_input': str (the user task/question)
    """
    suggestions = []
    
    # Standardize checking to lowercase
    deps = [d.lower() for d in context.get("dependencies", [])]
    raw_input_lower = context.get("raw_input", "").lower()
    
    # 1. FastAPI suggestions
    if "fastapi" in deps or "fastapi" in raw_input_lower:
        suggestions.extend(OBSERVABILITY_TEMPLATES["fastapi"])
        
    # 2. Django suggestions
    if "django" in deps or "django" in raw_input_lower:
        suggestions.extend(OBSERVABILITY_TEMPLATES["django"])
        
    # 3. Database suggestions
    db_keywords = ["db", "database", "sql", "sqlite", "postgres", "postgresql", "mysql", "sqlalchemy", "query", "queries"]
    if any(k in raw_input_lower for k in db_keywords) or any(k in deps for k in db_keywords):
        suggestions.extend(OBSERVABILITY_TEMPLATES["database"])
        
    # 4. Async suggestions
    async_keywords = ["async", "asyncio", "await", "concurrency", "concurrent"]
    if any(k in raw_input_lower for k in async_keywords) or any(k in deps for k in async_keywords):
        suggestions.extend(OBSERVABILITY_TEMPLATES["async"])
        
    # 5. Default suggestions (always include default suggestions or if no specific templates match)
    suggestions.extend(OBSERVABILITY_TEMPLATES["default"])
    
    # De-duplicate suggestions while maintaining order
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            unique_suggestions.append(s)
            
    return unique_suggestions
