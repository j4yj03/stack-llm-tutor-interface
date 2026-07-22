<p>Differenzieren Sie die Funktion \(f\) einmal nach {@v@}.</p>
<p>\(\large f({@v@})={@p@}\)</p>
<p>\(\large f'({@v@})=\,\) [[input:ans1]] [[validation:ans1]]</p>

<div style="margin-top: 1em; padding: 0.8em; border: 1px solid #ccc; background: #f7f7f7;">
  <strong>KI-Tutor:</strong><br>
 
  <a id="ai-tutor-dynamic-link"
     target="_blank"
     rel="noopener noreferrer"
     href="#">
     AI Tutor öffnen
  </a>
 
  <div id="ai-tutor-link-debug"
       style="margin-top: 0.5em; font-size: 0.85em; color: #666;">
    Link wird erzeugt ...
  </div>
</div>
 
<div id="stack-prt-feedback-area">
  [[feedback:Result]]
</div>
 
<script>
(function () {
    const BASE_URL = http://127.0.0.1:8000/start;
    const QID = "ableitung_kettenregel_exp_001";
    const DEFAULT_DIAGNOSIS = "unknown_error";
 
    function htmlEscape(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
 
    function findAns1Input() {
        return document.querySelector(
            'input[name*="ans1"], textarea[name*="ans1"]'
        );
    }
 
    function findDiagnosisCode() {
        const diagnosisElement = document.querySelector(".ai-tutor-diagnosis");
 
        if (!diagnosisElement) {
            return DEFAULT_DIAGNOSIS;
        }
 
        const code =
            diagnosisElement.getAttribute("data-diagnosis") ||
            diagnosisElement.textContent ||
            DEFAULT_DIAGNOSIS;
 
        return code.trim() || DEFAULT_DIAGNOSIS;
    }
 
    function updateTutorLink() {
        const input = findAns1Input();
        const link = document.getElementById("ai-tutor-dynamic-link");
        const debug = document.getElementById("ai-tutor-link-debug");
 
        if (!link) {
            return;
        }
 
        if (!input) {
            link.href = "#";
 
            if (debug) {
                debug.innerHTML = "ans1-Eingabefeld wurde nicht gefunden.";
                debug.style.color = "red";
            }
 
            return;
        }
 
        const answer = input.value || "";
        const encodedAnswer = encodeURIComponent(answer);
        const diagnosis = findDiagnosisCode();
 
        const url =
            BASE_URL
            + "?qid=" + encodeURIComponent(QID)
            + "&diagnosis=" + encodeURIComponent(diagnosis)
            + "&ans1=" + encodedAnswer
            + "&hint_level=1";
 
        link.href = url;
 
        if (debug) {
            debug.innerHTML =
                "Aktuelle Diagnose: <code>" + htmlEscape(diagnosis) + "</code><br>" +
                "Aktuelle Antwort: <code>" + htmlEscape(answer) + "</code><br>" +
                "Link: <code>" + htmlEscape(url) + "</code>";
        }
    }
 
    document.addEventListener("DOMContentLoaded", function () {
        const input = findAns1Input();
 
        if (input) {
            input.addEventListener("input", updateTutorLink);
        }
 
        updateTutorLink();
 
        const feedbackArea = document.getElementById("stack-prt-feedback-area");
 
        if (feedbackArea) {
            const observer = new MutationObserver(function () {
                updateTutorLink();
            });
 
            observer.observe(feedbackArea, {
                childList: true,
                subtree: true,
                characterData: true,
                attributes: true
            });
        }
    });
})();
</script>