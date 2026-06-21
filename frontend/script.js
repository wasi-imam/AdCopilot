// ── Element references ──
// Yeh saare DOM elements ko pakad ke rakhte hain, taaki baar-baar dhoondhna na pade
const adCopyInput      = document.getElementById("ad-copy-input");
const productDescInput = document.getElementById("product-desc-input");
const analyzeBtn       = document.getElementById("analyze-btn");

const loadingSection = document.getElementById("loading-section");
const errorSection   = document.getElementById("error-section");
const errorMessage   = document.getElementById("error-message");
const resultsSection = document.getElementById("results-section");

const resultGrade      = document.getElementById("result-grade");
const resultScore      = document.getElementById("result-score");
const resultOneLiner   = document.getElementById("result-one-liner");
const resultRewritten  = document.getElementById("result-rewritten-ad");
const resultChanges    = document.getElementById("result-changes");
const resultDimensions = document.getElementById("result-dimensions");
const resultGaps       = document.getElementById("result-gaps");
const benchmarkBtn      = document.getElementById("benchmark-btn");
const strategiesBtn     = document.getElementById("strategies-btn");

const benchmarkLoading  = document.getElementById("benchmark-loading");
const benchmarkSection  = document.getElementById("benchmark-section");
const benchmarkPosition = document.getElementById("benchmark-position");
const benchmarkInsight  = document.getElementById("benchmark-insight");
const benchmarkDims     = document.getElementById("benchmark-dimensions");

const strategiesLoading = document.getElementById("strategies-loading");
const strategiesSection = document.getElementById("strategies-section");
const strategiesRec     = document.getElementById("strategies-recommendation");
const strategiesCards   = document.getElementById("strategies-cards");

// Yeh /analyze ke result ko yaad rakhega, taaki /benchmark aur /strategies
// call karte waqt humein wahi data bhejna ho woh yahan se mil sake
let currentAnalysis = null;

// ── Button click listener ──
analyzeBtn.addEventListener("click", async () => {
    const adCopy = adCopyInput.value.trim();
    const productDesc = productDescInput.value.trim();

    // Basic validation — backend bhi validate karta hai, par frontend pe
    // jaldi feedback dena better UX hai
    if (!adCopy || !productDesc) {
        showError("Please fill in both fields.");
        return;
    }

    // UI state: loading dikhao, error/results chhupao
    hideAll();
    loadingSection.classList.remove("hidden");
    analyzeBtn.disabled = true;

    try {
        const response = await fetch("/api/v1/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ad_copy: adCopy,
                product_description: productDesc
            })
        });

        if (!response.ok) {
            // Backend ne error bheja (4xx/5xx) — detail nikalo
            const errData = await response.json();
            throw new Error(errData.detail || "Something went wrong.");
        }

        const data = await response.json();
        renderResults(data);

    } catch (err) {
        showError(err.message);
    } finally {
        loadingSection.classList.add("hidden");
        analyzeBtn.disabled = false;
    }
});

// ── Helper: sab sections chhupao ──
function hideAll() {
    loadingSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    resultsSection.classList.add("hidden");
}

// ── Helper: error dikhao ──
function showError(message) {
    hideAll();
    errorMessage.textContent = message;
    errorSection.classList.remove("hidden");
}

// ── Helper: results render karo ──
function renderResults(data) {
    const score = data.explainable_score;

    resultGrade.textContent    = `Grade: ${score.grade}`;
    resultScore.textContent    = `Score: ${score.total_score} / 100`;
    resultOneLiner.textContent = score.one_liner;
    resultRewritten.textContent = data.rewritten_ad;
    resultChanges.textContent   = data.changes_made;

    // Dimensions render karo
    resultDimensions.innerHTML = score.dimensions.map(dim => `
        <div class="dimension-item">
            <div class="dimension-header">
                <span>${dim.dimension}</span>
                <span>${dim.score}/10 — ${dim.rating}</span>
            </div>
            <div class="dimension-reason">${dim.reason}</div>
        </div>
    `).join("");

    // Gaps render karo
    resultGaps.innerHTML = data.gaps.map(gap => `
        <div class="gap-item severity-${gap.severity}">
            <strong>${gap.gap}</strong>
            <div class="dimension-reason">${gap.competitor_does}</div>
        </div>
    `).join("");

   resultsSection.classList.remove("hidden");

    // Is poore response ko yaad rakho, taaki benchmark/strategies ke
    // button click pe yahan se data nikal sakein
    currentAnalysis = data;
}

// ============================================================
// BENCHMARK
// ============================================================

benchmarkBtn.addEventListener("click", async () => {
    if (!currentAnalysis) return;

    benchmarkSection.classList.add("hidden");
    benchmarkLoading.classList.remove("hidden");
    benchmarkBtn.disabled = true;

    try {
        const dims = currentAnalysis.explainable_score.dimensions.map(d => ({
            dimension: d.dimension,
            score: d.score
        }));

        const response = await fetch("/api/v1/benchmark", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                analysis_id: currentAnalysis.analysis_id,
                user_score: currentAnalysis.explainable_score.total_score,
                dimensions: dims,
                product_description: currentAnalysis.product_description
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Benchmark failed.");
        }

        const data = await response.json();
        renderBenchmark(data);

    } catch (err) {
        showError(err.message);
    } finally {
        benchmarkLoading.classList.add("hidden");
        benchmarkBtn.disabled = false;
    }
});

function renderBenchmark(data) {
    benchmarkPosition.textContent = `${data.market_position} — ${data.percentile}th percentile`;
    benchmarkInsight.textContent  = data.insight;

    benchmarkDims.innerHTML = data.dimension_gaps.map(dg => `
        <div class="dimension-item">
            <div class="dimension-header">
                <span>${dg.dimension}</span>
                <span>You: ${dg.user_score} | Industry: ${dg.industry_avg}</span>
            </div>
            <div class="dimension-reason">Gap: ${dg.gap > 0 ? "+" : ""}${dg.gap}</div>
        </div>
    `).join("");

    benchmarkSection.classList.remove("hidden");
}

// ============================================================
// STRATEGIES
// ============================================================

strategiesBtn.addEventListener("click", async () => {
    if (!currentAnalysis) return;

    strategiesSection.classList.add("hidden");
    strategiesLoading.classList.remove("hidden");
    strategiesBtn.disabled = true;

    try {
        const response = await fetch("/api/v1/strategies", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                analysis_id: currentAnalysis.analysis_id,
                ad_copy: currentAnalysis.ad_copy,
                gaps: currentAnalysis.gaps,
                product_description: currentAnalysis.product_description
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Strategy generation failed.");
        }

        const data = await response.json();
        renderStrategies(data);

    } catch (err) {
        showError(err.message);
    } finally {
        strategiesLoading.classList.add("hidden");
        strategiesBtn.disabled = false;
    }
});

function renderStrategies(data) {
    strategiesRec.textContent = data.recommendation;

    strategiesCards.innerHTML = data.strategies.map(s => `
        <div class="strategy-card ${s.is_winner ? "winner" : ""}">
            <div class="strategy-header">
                <h4>${s.strategy_icon} ${s.strategy_name}</h4>
                ${s.is_winner ? '<span class="strategy-badge">Winner</span>' : ""}
            </div>
            <div class="strategy-score">Score: ${s.score ?? "N/A"} ${s.grade ? `(${s.grade})` : ""}</div>
            <div class="strategy-text">${s.rewritten_ad}</div>
        </div>
    `).join("");

    strategiesSection.classList.remove("hidden");
}