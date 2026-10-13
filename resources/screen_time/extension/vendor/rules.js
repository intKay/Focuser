/**
 * Rule matching. Pure functions over a compiled rule set — no browser APIs, so
 * every branch is testable without a extension harness.
 *
 * The desktop app compiles block lists into this shape and serves it at
 * `/api/rules`. Keyword, wildcard and URL-path rules exist here and *only*
 * here: a hosts file cannot express them, which is the whole reason the
 * extension is the preferred blocking path.
 */
export const EMPTY_RULES = {
    domains: new Set(),
    keywords: [],
    wildcards: [],
    urlPaths: [],
    blockEverything: false,
    allowed: new Set(),
    allowedWildcards: [],
    allowedPages: [],
    allowances: new Set(),
    categories: {},
};
/**
 * Reduce anything host-shaped to one comparable form.
 *
 * Accepts a bare host, a full URL, or something with credentials, a port or a
 * trailing dot. `www.` is stripped so a rule for `example.com` and a visit to
 * `www.example.com` are the same thing — the desktop app makes the same
 * assumption, and the two must agree or a rule silently misses.
 */
export function canonicalHost(raw) {
    const lowered = String(raw ?? "")
        .trim()
        .toLowerCase();
    // A scheme only counts at the very start, and the path goes before the
    // credentials: an `@` after the first slash is part of the page
    // (youtube.com/@name). The Rust side parses it the same way.
    let host = lowered.replace(/^[a-z0-9+-]+:\/\//, "").split(/[/?#]/)[0] ?? "";
    host = host.slice(host.lastIndexOf("@") + 1);
    const colon = host.lastIndexOf(":");
    if (colon > 0)
        host = host.slice(0, colon);
    host = host.replace(/\.+$/, "");
    return host.startsWith("www.") ? host.slice(4) : host;
}
/**
 * Whether a set of rule hosts covers this host — exactly, or as a parent.
 *
 * A rule for `example.com` covers `mail.example.com`. It must not cover
 * `notexample.com`, which is why this walks label boundaries rather than
 * testing string suffixes.
 */
export function setCovers(set, host) {
    const canonical = canonicalHost(host);
    if (!canonical)
        return false;
    if (set.has(canonical))
        return true;
    const parts = canonical.split(".");
    for (let i = 1; i < parts.length; i++) {
        if (set.has(parts.slice(i).join(".")))
            return true;
    }
    return false;
}
export function canonicalSet(list) {
    const set = new Set();
    for (const entry of list ?? []) {
        const host = canonicalHost(entry);
        if (host)
            set.add(host);
    }
    return set;
}
/** Glob match. `*` is any run, `?` is one character. */
export function matchWildcard(pattern, value) {
    const escaped = pattern
        .replace(/[.+^${}()|[\]\\]/g, "\\$&")
        .replace(/\*/g, ".*")
        .replace(/\?/g, ".");
    try {
        return new RegExp(`^${escaped}$`).test(value);
    }
    catch {
        // A pattern that will not compile blocks nothing rather than everything.
        return false;
    }
}
/**
 * A wildcard against a hostname. `*.youtube.com` covers `youtube.com` too.
 *
 * People write the `*.` form meaning "the site", and a pattern that skipped the
 * apex just looked broken. `focuser_common::host::wildcard_matches` is the same
 * rule on the Rust side; the two have to agree or a rule silently misses.
 */
export function matchHostWildcard(pattern, hostname) {
    const canonical = canonicalHost(hostname);
    if (!canonical)
        return false;
    // Both the host as given and its canonical form: a glob may be aiming at the
    // `www.` label that canonicalHost removes.
    const raw = String(hostname ?? "")
        .trim()
        .toLowerCase();
    const glob = pattern.trim().toLowerCase();
    if (matchWildcard(glob, raw) || matchWildcard(glob, canonical))
        return true;
    const apex = glob.startsWith("*.") ? glob.slice(2) : "";
    if (!apex || /[*?]/.test(apex))
        return false;
    return setCovers(new Set([apex]), canonical);
}
export function compile(rules) {
    if (!rules)
        return EMPTY_RULES;
    return {
        scopes: rules.scopes?.map((s) => ({
            rules: compile(s.rules),
            sharedPermits: s.shared_permits,
            scheduled: s.scheduled,
        })),
        domains: canonicalSet(rules.blocked_domains),
        keywords: (rules.blocked_keywords ?? []).map((k) => k.toLowerCase()),
        wildcards: rules.blocked_wildcards ?? [],
        urlPaths: (rules.blocked_url_paths ?? []).map((p) => p.toLowerCase()),
        blockEverything: rules.block_entire_internet ?? false,
        allowed: canonicalSet(rules.allowed_domains),
        allowedWildcards: rules.allowed_wildcards ?? [],
        allowedPages: (rules.allowed_url_paths ?? []).flatMap(compilePage),
        allowances: canonicalSet(rules.allowance_domains),
        categories: rules.domain_categories ?? {},
    };
}
/** `host/path` as the app sends it. An entry with no path is dropped. */
function compilePage(entry) {
    const slash = entry.indexOf("/");
    const host = canonicalHost(entry);
    if (slash === -1 || !host)
        return [];
    return [{ host, page: entry.slice(slash).toLowerCase() }];
}
/**
 * On the allowed page or under it. `/r/programming` covers
 * `/r/programming/comments` but not `/r/programminghumor`, so the match has
 * to end on a boundary.
 */
function onPage(allowed, hostname, url) {
    const host = canonicalHost(hostname);
    if (host !== allowed.host && !host.endsWith(`.${allowed.host}`))
        return false;
    let path;
    try {
        const parsed = new URL(url);
        path = (parsed.pathname + parsed.search).toLowerCase();
    }
    catch {
        return false;
    }
    if (!path.startsWith(allowed.page))
        return false;
    const next = path[allowed.page.length];
    return next === undefined || "/?&".includes(next);
}
export function isAllowed(rules, hostname, url = "") {
    if (setCovers(rules.allowed, hostname))
        return true;
    if (rules.allowedWildcards.some((pattern) => matchHostWildcard(pattern, hostname)))
        return true;
    return rules.allowedPages.some((page) => onPage(page, hostname, url));
}
/**
 * Decide whether a navigation is blocked, and by what.
 *
 * Exceptions win over every rule, including "block the entire internet" —
 * an allowance that cannot be honoured is not an allowance.
 */
export function match(rules, hostname, url) {
    const host = canonicalHost(hostname);
    const lowerUrl = (url ?? "").toLowerCase();
    // With scopes, each list brings its own exceptions. The flat ones are every
    // list's mixed together, for an extension older than this one, so only the
    // allowances are read from the top level here.
    if (rules.scopes?.length) {
        const applicable = rules.scopes
            .map((s) => ({ ...s, hit: match(s.rules, hostname, url) }))
            .filter((s) => s.hit);
        const shared = applicable.some((s) => s.sharedPermits !== null);
        for (const scope of applicable) {
            if (scope.sharedPermits === true)
                continue;
            if (!shared && !scope.scheduled && setCovers(rules.allowances, hostname))
                continue;
            return scope.hit;
        }
        return null;
    }
    if (isAllowed(rules, hostname, url))
        return null;
    if (rules.blockEverything)
        return { reason: "everything", target: host };
    if (setCovers(rules.domains, host))
        return { reason: "domain", target: host };
    for (const keyword of rules.keywords) {
        if (lowerUrl.includes(keyword))
            return { reason: "keyword", target: keyword };
    }
    for (const path of rules.urlPaths) {
        if (lowerUrl.includes(path))
            return { reason: "url-path", target: path };
    }
    for (const raw of rules.wildcards) {
        if (matchHostWildcard(raw, hostname) || matchWildcard(raw.toLowerCase(), lowerUrl)) {
            return { reason: "wildcard", target: raw };
        }
    }
    return null;
}
export function isBlocked(rules, hostname, url) {
    return match(rules, hostname, url) !== null;
}
/** Pages the extension must never touch: its own, and the browser's. */
export function isInternalUrl(protocol) {
    return (protocol === "chrome:" ||
        protocol === "chrome-extension:" ||
        protocol === "about:" ||
        protocol === "moz-extension:" ||
        protocol === "edge:" ||
        protocol === "data:" ||
        protocol === "view-source:");
}
/**
 * How the block is counted in statistics.
 *
 * Keyword matches are keyed by the keyword, not the host, so "blocked 40 times
 * by the word `casino`" stays one row instead of forty different domains.
 */
export function trackingKey(hit) {
    return hit.reason === "keyword" || hit.reason === "wildcard" || hit.reason === "url-path"
        ? `kw:${hit.target.toLowerCase()}`
        : hit.target.toLowerCase();
}
/** How many distinct things the current rules block, for the toolbar badge. */
export function ruleCount(rules) {
    return (rules.domains.size + rules.keywords.length + rules.urlPaths.length + rules.wildcards.length);
}
