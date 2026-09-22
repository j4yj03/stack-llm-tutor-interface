"use strict";

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const readSnippet = (name) => readFileSync(path.join(__dirname, "../moodle", name), "utf8");
const source = readSnippet("fragetext_castext.html");
const prt = readSnippet("prt_feedback.html");
const diagnosis = "missing_chain_rule_inner_derivative";
const entities = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'" };
const decodeHtml = (text) => text.replace(/&(amp|lt|gt|quot|#39);/g, (entity) => entities[entity]);
const escapeHtml = (text) => text.replace(/[&<>"']/g,
    (char) => Object.keys(entities).find((entity) => entities[entity] === char));
const readBranch = (code) => {
    const marker = prt.indexOf('data-diagnosis="' + code + '"');
    assert.ok(marker >= 0, "missing marker for " + code);
    const start = prt.lastIndexOf("<div", marker);
    const end = prt.indexOf("</div>", marker) + "</div>".length;
    return prt.slice(start, end);
};
const feedback = (answer, code = diagnosis, debug = true) => {
    let branch = readBranch(diagnosis)
        .replace(diagnosis, () => escapeHtml(code))
        .replace("[[entityescape]]{#ans1#}[[/entityescape]]", () => escapeHtml(answer));
    // STACK-Rendere Simulation des [[if test='debug>0']]-Blocks: bei
    // debug=0/geloescht bleibt der Else-Zweig leer (kein Marker).
    if (!debug) {
        branch = branch.replace(
            /<p><span class="ai-tutor-diagnosis"[\s\S]*?<\/span><\/p>/, ""
        );
    }
    return branch
        .replace(/\[\[if[^\]]*\]\]/g, "")
        .replace(/\[\[\/if\]\]/g, "");
};
const enableTimers = (t) => t.mock.timers.enable({ apis: ["setTimeout"] });
const flush = () => new Promise(setImmediate);
const tick = async (t, ms) => {
    t.mock.timers.tick(ms);
    for (let round = 0; round < 3; round++) {
        await flush();
    }
};

// CASText and DOM test doubles only; no claim to execute Maxima or browser HTML parsing.
function sandbox({ answer = "x+1", html = null, p = "-5*%e^(x^2-2*%e^x)", v = "x",
    model = "", prefix = "q1:-quid_", connectionError = false, validationListener = true } = {}) {
    const input = { value: answer, addEventListener(type, callback) {
        assert.equal(type, "change");
        this.onchange = callback;
    } };
    const writes = [];
    const reads = [];
    const warnings = [];
    const validationCallbacks = [];
    let getContent = () => Promise.resolve(html);
    let script = source.match(/\[\[javascript\]\]([\s\S]*?)\[\[\/javascript\]\]/)[1];
    script = script.replace(/\[\[jsstring\]\]([\s\S]*?)\[\[\/jsstring\]\]/g, (_, text) => {
        const raw = text.replace(/\{#([pv])#\}/g, (_, name) => ({ p, v })[name]);
        // PHP json_encode (used by JSString) also escapes slashes in script literals.
        return JSON.stringify(raw).replace(/\//g, "\\/");
    }).replace(/\[\[quid id='([^']+)'\/\]\]/g, (_, id) => prefix + id)
        .replace('const MODEL = "";', () => "const MODEL = " + JSON.stringify(model) + ";");
    assert.doesNotMatch(script, /\[\[|\{[#@]/);
    const ready = vm.runInNewContext(script, {
        URL,
        setTimeout,
        clearTimeout,
        console: { warn: (message) => warnings.push(message) },
        document: {
            getElementById(id) {
                assert.equal(id, "sandbox-mirror");
                return input;
            },
            createElement(tag) {
                assert.equal(tag, "template");
                const template = { innerHTML: "" };
                template.content = { querySelectorAll(selector) {
                    assert.equal(selector, ".ai-tutor-diagnosis");
                    return Array.from(template.innerHTML.matchAll(/<span\b([^>]*)>([\s\S]*?)<\/span>/g))
                        .filter((match) => /class="ai-tutor-diagnosis"/.test(match[1]))
                        .map((match) => ({
                            textContent: decodeHtml(match[2].replace(/<[^>]*>/g, "")),
                            getAttribute(name) {
                                assert.equal(name, "data-diagnosis");
                                const attr = match[1].match(/data-diagnosis="([^"]*)"/);
                                return attr ? decodeHtml(attr[1]) : null;
                            },
                        }));
                } };
                return template;
            },
        },
        stack_js: {
            request_access_to_input(...args) {
                assert.deepEqual(args, ["ans1", true, true]);
                return connectionError ? Promise.reject(new Error("No input")) : Promise.resolve("sandbox-mirror");
            },
            get_content(id) {
                assert.equal(id, prefix + "ai-tutor-feedback");
                reads.push(id);
                return getContent();
            },
            switch_content(id, content) {
                assert.equal(id, prefix + "ai-tutor-link");
                writes.push(content);
            },
            register_validation_state_listener(name, callback, limitToQuestion) {
                assert.equal(name, "ans1");
                assert.equal(limitToQuestion, true);
                if (!validationListener) {
                    throw new Error("register_validation_state_listener fehlt");
                }
                validationCallbacks.push(callback);
            },
        },
    }, { filename: "fragetext_castext.rendered.js", timeout: 1000 });
    return {
        ready, reads, writes, warnings, script,
        get validationCount() { return validationCallbacks.length; },
        validation(complete) {
            assert.ok(validationCallbacks.length > 0, "no validation listener registered");
            return Promise.all(
                [...validationCallbacks].map(
                    (callback) => callback(complete, complete ? true : null, "ans1")
                )
            );
        },
        change(value) { input.value = value; input.onchange(); },
        setFeedback(value) { getContent = () => Promise.resolve(value); },
        setFetch(callback) { getContent = callback; },
        output() { return writes.at(-1); },
        url() {
            const href = writes.at(-1).match(/<a\b[^>]*href="([^"]+)"/);
            return href ? new URL(decodeHtml(href[1])) : null;
        },
    };
}

test("field snippets preserve mathematics and use only STACK sandbox APIs", () => {
    const variables = readSnippet("question_variables.txt").replace(/\r/g, "");
    assert.match(variables,
        /^v:x;\nrdm:-1-rand\(9\);\nrdm2: rand_with_prohib\(-9,9,\[0\]\);\npp:v\^-rdm\+rdm\*exp\(v\);\np:rdm2\*exp\(pp\);/);
    assert.equal((variables.match(/\/\*/g) || []).length,
        (variables.match(/\*\//g) || []).length);
    assert.doesNotMatch(
        variables.replace(/\/\*[\s\S]*?\*\//g, ""),
        /urlencode_basic|validate_listlength/
    );
    assert.match(source, /\[\[input:ans1\]\] \[\[validation:ans1\]\]/);
    assert.doesNotMatch(source, /\[\[feedback:/);
    assert.match(prt, /\[\[quid id='ai-tutor-feedback'\/\]\]/);
    assert.equal(source.match(/\[\[javascript\]\]/g).length, 1);
    assert.equal(source.match(/http:\/\/127\.0\.0\.1:8000\/start/g).length, 1);
    assert.doesNotMatch(source, /ai-tutor-refresh|register_external_button_listener/);
    assert.match(source, /KI-Tutor &ouml;ffnen \(neuer Tab\)/);
    assert.match(source, /class="btn btn-primary" role="button"/);
    assert.doesNotMatch(source, /<script|parent\.|window\.|document\.querySelector|MutationObserver|setInterval|fetch\(|import /);
    assert.match(prt, /\[\[entityescape\]\]\{#ans1#\}\[\[\/entityescape\]\]/);
    assert.match(source, /register_validation_state_listener\("ans1", \(complete\) =>/);
    assert.match(source, /scheduleProbes\(\[800, 3000\]\)/);
    assert.match(source, /searchParams\.set\("funktion", FUNKTION\)/);
    assert.doesNotMatch(source, /set\("question_text"/);
    assert.equal((prt.match(/class="ai-tutor-diagnosis"/g) || []).length, 2);
    assert.equal((prt.match(/\[\[quid id='ai-tutor-feedback'\/\]\]/g) || []).length, 2);
    assert.equal((prt.match(/\[\[if test='debug>0'\]\]/g) || []).length, 2);
    assert.match(variables, /debug:0;/);
    assert.match(prt, /data-diagnosis="wrong_derivative_inner_exp"/);
    assert.match(prt, /Die Ableitung von \{@pp@\} wurde vermutlich falsch bestimmt\./);
});

test("URL query and HTML round-trip special characters without leaking markup", async () => {
    const answer = 'x+%e & <img src=x onerror="bad()"> \\ "\'\n\u00f6';
    const app = sandbox({ answer, html: feedback(answer) });
    await app.ready;
    const url = app.url();
    assert.equal(url.origin + url.pathname, "http://127.0.0.1:8000/start");
    assert.equal(url.searchParams.get("qid"), "ableitung_kettenregel_exp_001");
    assert.equal(url.searchParams.get("ans1"), answer);
    assert.equal(url.searchParams.get("funktion"), "f(x)=-5*%e^(x^2-2*%e^x)");
    assert.equal(url.searchParams.get("diagnosis"), diagnosis);
    assert.equal(url.searchParams.get("hint_level"), "1");
    assert.equal(url.searchParams.has("model"), false);
    for (const encoded of ["%2B", "%25", "%26"]) assert.ok(url.search.includes(encoded));
    assert.match(app.output(), /target="_blank" rel="noopener noreferrer"/);
    assert.match(app.output(), /&amp;diagnosis=/);
    assert.doesNotMatch(app.output(), /<img|<script|onerror=/);
    assert.equal(decodeHtml(app.output().match(/<code style="[^"]*">([^<]+)<\/code>/)[1]), url.href);
});

test("instantiated function is transported safely as strings", async () => {
    for (const [p, v] of [["-5*%e^(x^2-2*%e^x)", "x"], ["9*%e^(y^9-9*%e^y)", "y"],
        ['"</script><script>throw 42</script>\\\n + % & \u00e4', "x"]]) {
        const app = sandbox({ p, v, model: "test-model" });
        await app.ready;
        assert.equal(app.url().searchParams.get("funktion"), "f(" + v + ")=" + p);
        assert.equal(app.url().searchParams.has("question_text"), false);
        assert.equal(app.url().searchParams.get("model"), "test-model");
        assert.doesNotMatch(app.script, /<\/script>/i);
    }
});

test("missing, mismatched, duplicate and malformed PRT markers stay unknown", async () => {
    for (const html of [null, "", "<p>No diagnosis</p>", feedback("old answer"),
        feedback("x+1") + feedback("x+1"), feedback("x+1", "bad\ncode"),
        feedback("x+1", ""), feedback("x+1", "a".repeat(101)),
        '<span class="ai-tutor-diagnosis" data-diagnosis="' + diagnosis + '"> </span>']) {
        const app = sandbox({ html });
        await app.ready;
        assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error", String(html));
    }
});

test("every input change rebuilds the link automatically; bounded probes adopt fresh feedback", async (t) => {
    enableTimers(t);
    const app = sandbox({ html: feedback("x+1") });
    await app.ready;
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    assert.equal(app.reads.length, 1);
    app.change("x+2");
    assert.equal(app.url().searchParams.get("ans1"), "x+2");
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    assert.equal(app.reads.length, 1);
    await tick(t, 800);
    assert.equal(app.reads.length, 2);
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.setFeedback(feedback("x+2"));
    await tick(t, 2200);
    assert.equal(app.reads.length, 3);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    app.change("x+1");
    app.change("x+2");
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.change("   ");
    assert.equal(app.url(), null);
});

test("late PRT rendering and a fresh sandbox after re-render are supported", async (t) => {
    enableTimers(t);
    const app = sandbox();
    await app.ready;
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.setFeedback(feedback("x+1"));
    await app.validation(true);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    const other = sandbox({ prefix: "q2:-quid_", answer: "x+3", html: feedback("x+1") });
    await other.ready;
    assert.equal(other.url().searchParams.get("diagnosis"), "unknown_error");
    assert.equal(app.url().searchParams.get("ans1"), "x+1");
});

test("overlapping reads are suppressed and responses after edits are discarded", async (t) => {
    enableTimers(t);
    const app = sandbox();
    await app.ready;
    let complete;
    app.setFetch(() => new Promise((resolve) => { complete = resolve; }));
    const first = app.validation(true);
    await app.validation(true);
    assert.equal(app.reads.length, 2);
    app.change("x+2");
    app.change("x+1");
    complete(feedback("x+1"));
    await first;
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.setFeedback(feedback("x+1"));
    await app.validation(true);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
});

test("limits never truncate the function or produce a link for empty input", async () => {
    const empty = sandbox({ answer: "" });
    await empty.ready;
    assert.equal(empty.url(), null);
    const base = sandbox({ p: "" });
    await base.ready;
    const length = base.url().searchParams.get("funktion").length;
    for (const size of [5000, 5001]) {
        for (const char of ["x", "\u{1d465}"]) {
            const app = sandbox({ p: char.repeat(size - length) });
            await app.ready;
            if (size === 5000) assert.equal(Array.from(app.url().searchParams.get("funktion")).length, 5000);
            else assert.equal(app.url(), null);
        }
    }
});

test("bridge errors fail safely without exposing input or upstream error text", async (t) => {
    enableTimers(t);
    const app = sandbox({ html: feedback("x+1") });
    await app.ready;
    app.setFetch(() => Promise.reject(new Error("private upstream detail")));
    await app.validation(true);
    assert.equal(app.warnings.length, 1);
    assert.doesNotMatch(app.warnings[0], /private upstream detail|x\+1/);
    // A failed probe never demotes: the retained binding still matches the
    // unchanged answer exactly.
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    const unavailable = sandbox({ connectionError: true });
    await unavailable.ready;
    assert.equal(unavailable.url(), null);
    assert.match(unavailable.output(), /STACK-JS/);
    assert.equal(unavailable.reads.length, 0);
});

test("completed validation adopts the diagnosis automatically", async (t) => {
    enableTimers(t);
    const app = sandbox({ html: feedback("x+1") });
    await app.ready;
    assert.equal(app.validationCount, 1);
    app.change("x+2");
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.setFeedback(feedback("x+2"));
    await app.validation(true);
    await flush();
    assert.equal(app.reads.length, 2);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    await tick(t, 1200);
    assert.equal(app.reads.length, 3);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    await tick(t, 2300);
    assert.equal(app.reads.length, 4);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    await app.validation(false);
    assert.equal(app.reads.length, 4);
});

test("scheduled probes stay bounded instead of polling forever", async (t) => {
    enableTimers(t);
    const app = sandbox({ html: null });
    await app.ready;
    assert.equal(app.reads.length, 1);
    app.change("x+9");
    await tick(t, 800);
    assert.equal(app.reads.length, 2);
    await tick(t, 2200);
    assert.equal(app.reads.length, 3);
    await tick(t, 60000);
    assert.equal(app.reads.length, 3);
});

test("missing validation listener API degrades to change handling and follow-up probes", async (t) => {
    enableTimers(t);
    const app = sandbox({ html: feedback("x+1"), validationListener: false });
    await app.ready;
    assert.equal(app.validationCount, 0);
    assert.equal(app.warnings.length, 1);
    assert.match(app.warnings[0], /Automatische Diagnoseaktualisierung/);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
    app.change("x+2");
    assert.equal(app.url().searchParams.get("diagnosis"), "unknown_error");
    app.setFeedback(feedback("x+2"));
    await tick(t, 800);
    assert.equal(app.url().searchParams.get("diagnosis"), diagnosis);
});

test("debug variable gates marker transport and code display", async (t) => {
    enableTimers(t);
    // debug=0/geloescht: kein Marker -> unknown_error, keine Codeanzeige.
    const off = sandbox({ html: feedback("x+1", diagnosis, false) });
    await off.ready;
    assert.equal(off.url().searchParams.get("diagnosis"), "unknown_error");
    assert.doesNotMatch(off.output(), /PRT-Diagnose:/);
    off.setFeedback(feedback("x+1", diagnosis, false));
    await off.validation(true);
    await flush();
    assert.equal(off.url().searchParams.get("diagnosis"), "unknown_error");
    assert.doesNotMatch(off.output(), /PRT-Diagnose:/);
    // Auch nach erfolglosen Abrufen bleibt der Parameter unknown_error.
    assert.match(off.url().search, /diagnosis=unknown_error/);

    // debug=1: Marker wird uebertragen, Code uebernommen und gezeigt.
    const on = sandbox({ html: feedback("x+1", diagnosis, true) });
    await on.ready;
    assert.equal(on.url().searchParams.get("diagnosis"), diagnosis);
    assert.match(on.output(), /PRT-Diagnose: <code>/);
    assert.match(on.output(), new RegExp(diagnosis));
});
