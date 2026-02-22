import { useState, useEffect } from "react";

export default function PriceHawkProComplete() {
  const [flipkartUrl, setFlipkartUrl] = useState("");
  const [amazonUrl, setAmazonUrl] = useState("");
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("compare");
  const [history, setHistory] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [expandedReviews, setExpandedReviews] = useState({});

  // ── Load history from in-memory state (no localStorage) ──────────────────
  // History is maintained in React state throughout the session

  // ── Fetch dashboard data ──────────────────────────────────────────────────
  const fetchDashboard = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/dashboard");
      const data = await res.json();
      setDashboardData(data);
    } catch {
      // Dashboard is optional; use local history if backend is unavailable
      setDashboardData({ fallback: true });
    }
  };

  useEffect(() => {
    if (activeTab === "dashboard") fetchDashboard();
  }, [activeTab]);

  // ── Compare ───────────────────────────────────────────────────────────────
  const compareProducts = async () => {
    if (!flipkartUrl.trim() && !amazonUrl.trim()) {
      setError("Please enter at least one product URL");
      return;
    }

    setLoading(true);
    setComparison(null);
    setError("");
    setShowResults(false);

    try {
      const params = new URLSearchParams();
      if (flipkartUrl.trim()) params.append("flipkart_url", flipkartUrl.trim());
      if (amazonUrl.trim())   params.append("amazon_url",   amazonUrl.trim());

      const res  = await fetch(`http://127.0.0.1:5000/api/compare?${params}`);
      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setComparison(data);
        setShowResults(true);
        const entry = { id: Date.now(), timestamp: new Date().toLocaleString(), ...data };
        setHistory(prev => [entry, ...prev.slice(0, 19)]);
      }
    } catch {
      setError("❌ Cannot connect to backend. Make sure the Flask server is running on port 5000.");
    }

    setLoading(false);
  };

  const toggleReviews = (platform) =>
    setExpandedReviews(prev => ({ ...prev, [platform]: !prev[platform] }));

  // ── Star renderer ─────────────────────────────────────────────────────────
  const renderStars = (rating) => {
    if (!rating) return null;
    const full    = Math.floor(rating);
    const hasHalf = rating % 1 >= 0.5;
    const empty   = 5 - full - (hasHalf ? 1 : 0);
    return (
      <div className="stars-container">
        {[...Array(full)].map((_, i)  => <span key={`f${i}`} className="star filled">★</span>)}
        {hasHalf                        && <span key="h"       className="star half">★</span>}
        {[...Array(empty)].map((_, i) => <span key={`e${i}`} className="star empty">★</span>)}
      </div>
    );
  };

  // ── Reviews block ─────────────────────────────────────────────────────────
  const renderReviews = (product, platform) => {
    if (!product?.reviews?.length) return null;
    const isExpanded   = expandedReviews[platform];
    const reviewsToShow = isExpanded ? product.reviews : product.reviews.slice(0, 3);

    return (
      <div className="reviews-section">
        <div className="reviews-header">
          <span className="reviews-title">💬 Customer Reviews ({product.reviews.length})</span>
          {product.reviews.length > 3 && (
            <button className="reviews-toggle" onClick={() => toggleReviews(platform)}>
              {isExpanded ? "Show Less ▲" : `Show All ${product.reviews.length} ▼`}
            </button>
          )}
        </div>
        <div className="reviews-list">
          {reviewsToShow.map((rev, idx) => (
            <div key={idx} className="review-card">
              <div className="review-header">
                {renderStars(rev.rating)}
                <span className="review-rating-num">{rev.rating}/5</span>
              </div>
              <div className="review-text">{rev.text}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ── Product card ──────────────────────────────────────────────────────────
  const renderProductCard = (product, platform) => {
    if (!product) return null;
    const isWinner = comparison?.winner === platform;
    const platformColors = {
      flipkart: { primary: "#2874f0", gradient: "linear-gradient(135deg,#2874f0,#1a5cc5)" },
      amazon:   { primary: "#ff9900", gradient: "linear-gradient(135deg,#ff9900,#e68a00)" },
    };
    const colors = platformColors[platform];

    return (
      <div className={`product-card ${isWinner ? "winner-card" : ""}`}>
        {isWinner && (
          <div className="winner-crown">
            <div className="crown-icon">👑</div>
            <div className="crown-text">BEST VALUE</div>
          </div>
        )}

        <div className="platform-badge" style={{ background: colors.gradient }}>
          <span className="platform-icon">{platform === "flipkart" ? "🛒" : "📦"}</span>
          <span className="platform-name">{platform === "flipkart" ? "Flipkart" : "Amazon"}</span>
        </div>

        {product.image && (
          <div className="product-image-container">
            <div className="image-glow" style={{ background: colors.gradient }}></div>
            <img src={product.image} alt="product" className="product-image" />
          </div>
        )}

        <div className="product-info">
          <h3 className="product-title">{product.title}</h3>

          <div className="price-section">
            <div className="price-label">Price</div>
            <div className="price-value">{product.price || "N/A"}</div>
          </div>

          {product.rating && (
            <div className="rating-section">
              {renderStars(product.rating)}
              <span className="rating-value">{product.rating}/5</span>
            </div>
          )}

          {product.ai_score !== undefined && (
            <div className="ai-score-section">
              <div className="ai-score-header">
                <span className="ai-icon">🤖</span>
                <span className="ai-label">AI Analysis Score</span>
              </div>

              <div className="score-circle-container">
                <svg className="score-circle" viewBox="0 0 120 120">
                  <defs>
                    <linearGradient id={`grad-${platform}`} x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%"   style={{ stopColor: "#6366f1" }} />
                      <stop offset="100%" style={{ stopColor: "#8b5cf6" }} />
                    </linearGradient>
                  </defs>
                  <circle className="score-circle-bg" cx="60" cy="60" r="50" />
                  <circle
                    className="score-circle-progress" cx="60" cy="60" r="50"
                    stroke={`url(#grad-${platform})`}
                    strokeDasharray={`${product.ai_score * 3.14} 314`}
                  />
                  <text x="60" y="55" className="score-text">{product.ai_score}</text>
                  <text x="60" y="70" className="score-subtext">/100</text>
                </svg>
              </div>

              <div className="ai-verdict">{product.ai_verdict}</div>

              {product.ai_reasons?.length > 0 && (
                <div className="ai-reasons">
                  {product.ai_reasons.map((r, i) => (
                    <div key={i} className="reason-item">
                      <span className="reason-icon">✓</span>
                      <span className="reason-text">{r}</span>
                    </div>
                  ))}
                </div>
              )}

              {product.ai_breakdown && (
                <div className="score-breakdown">
                  <div className="breakdown-title">Score Breakdown</div>
                  <div className="breakdown-bars">
                    {[
                      { label: "⭐ Rating",    score: product.ai_breakdown.rating_score    || 0, max: 40 },
                      { label: "💬 Reviews",   score: product.ai_breakdown.sentiment_score || 0, max: 30 },
                      { label: "📊 Categories",score: product.ai_breakdown.category_score  || 0, max: 20 },
                      { label: "🔧 Specs",     score: product.ai_breakdown.specs_score     || 0, max: 10 },
                    ].map((item, i) => (
                      <div key={i} className="breakdown-item">
                        <div className="breakdown-label">
                          <span>{item.label}</span>
                          <span>{item.score}/{item.max}</span>
                        </div>
                        <div className="breakdown-bar">
                          <div className="breakdown-fill" style={{ width: `${(item.score / item.max) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Specifications — now includes display */}
          {(product.ram || product.storage || product.processor ||
            product.camera || product.battery || product.display) && (
            <div className="specs-section">
              <div className="specs-title">📱 Specifications</div>
              <div className="specs-grid">
                {[
                  { icon: "💾", label: "RAM",       value: product.ram },
                  { icon: "💿", label: "Storage",   value: product.storage },
                  { icon: "🖥️", label: "Display",   value: product.display },
                  { icon: "🔧", label: "Processor", value: product.processor?.substring(0, 24) },
                  { icon: "📷", label: "Camera",    value: product.camera },
                  { icon: "🔋", label: "Battery",   value: product.battery },
                ].filter(s => s.value).map((s, i) => (
                  <div key={i} className="spec-item">
                    <span className="spec-icon">{s.icon}</span>
                    <div className="spec-content">
                      <div className="spec-label">{s.label}</div>
                      <div className="spec-value">{s.value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Category Ratings */}
          {product.category_ratings && Object.keys(product.category_ratings).length > 0 && (
            <div className="category-section">
              <div className="category-title">📊 Category Ratings</div>
              <div className="category-ratings">
                {Object.entries(product.category_ratings).map(([cat, val]) => (
                  <div key={cat} className="category-item">
                    <div className="category-header">
                      <span className="category-name">{cat}</span>
                      <span className="category-score">{val}/5</span>
                    </div>
                    <div className="category-bar">
                      <div className="category-fill" style={{ width: `${(val / 5) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {renderReviews(product, platform)}
        </div>
      </div>
    );
  };

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div className="pricehawk-app">
      <div className="animated-bg">
        <div className="bg-gradient"></div>
        <div className="bg-circles">
          <div className="circle circle-1"></div>
          <div className="circle circle-2"></div>
          <div className="circle circle-3"></div>
        </div>
      </div>

      <div className="app-content">
        <header className="app-header">
          <div className="logo-container">
            <div className="logo-icon">🦅</div>
            <h1 className="logo-text">
              <span className="logo-price">Price</span>
              <span className="logo-hawk">Hawk</span>
              <span className="logo-pro">Pro</span>
            </h1>
          </div>
          <p className="tagline">AI-Powered Smart Shopping Comparison</p>

          <div className="tabs">
            {[
              { key: "compare",   icon: "⚖️",  label: "Compare" },
              { key: "history",   icon: "📜",  label: "History" },
              { key: "dashboard", icon: "📊",  label: "Dashboard" },
            ].map(t => (
              <button
                key={t.key}
                className={`tab ${activeTab === t.key ? "active" : ""}`}
                onClick={() => setActiveTab(t.key)}
              >
                <span className="tab-icon">{t.icon}</span>
                <span className="tab-text">{t.label}</span>
                {t.key === "history" && history.length > 0 && (
                  <span className="tab-badge">{history.length}</span>
                )}
              </button>
            ))}
          </div>
        </header>

        {/* ── Compare Tab ─────────────────────────────────────────────────── */}
        {activeTab === "compare" && (
          <div className="compare-section">
            <div className="input-section">
              <div className="input-group">
                <label className="input-label">
                  <span className="label-icon">🛒</span>
                  <span className="label-text">Flipkart Product URL</span>
                </label>
                <input
                  type="text"
                  className="url-input flipkart-input"
                  placeholder="https://www.flipkart.com/..."
                  value={flipkartUrl}
                  onChange={e => setFlipkartUrl(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && compareProducts()}
                />
              </div>

              <div className="input-divider">
                <span className="divider-text">AND / OR</span>
              </div>

              <div className="input-group">
                <label className="input-label">
                  <span className="label-icon">📦</span>
                  <span className="label-text">Amazon India Product URL</span>
                </label>
                <input
                  type="text"
                  className="url-input amazon-input"
                  placeholder="https://www.amazon.in/..."
                  value={amazonUrl}
                  onChange={e => setAmazonUrl(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && compareProducts()}
                />
              </div>

              <button className="compare-button" onClick={compareProducts} disabled={loading}>
                {loading ? (
                  <><span className="button-spinner"></span><span>Analyzing…</span></>
                ) : (
                  <><span className="button-icon">⚡</span><span>Compare Products</span></>
                )}
              </button>
            </div>

            {error && (
              <div className="error-message">
                <span className="error-icon">⚠️</span>
                <span className="error-text">{error}</span>
              </div>
            )}

            {loading && (
              <div className="loading-container">
                <div className="loading-animation">
                  <div className="loading-hawk">🦅</div>
                  <div className="loading-text">Scraping & analyzing products…</div>
                  <div className="loading-bar">
                    <div className="loading-progress"></div>
                  </div>
                  <div className="loading-steps">
                    <span>📡 Fetching pages</span>
                    <span>🔍 Extracting data</span>
                    <span>🤖 AI scoring</span>
                  </div>
                </div>
              </div>
            )}

            {comparison && !loading && showResults && (
              <div className="results-section">
                {comparison.winner && (
                  <div className={`winner-banner ${comparison.winner}`}>
                    <div className="banner-content">
                      {comparison.winner === "tie" ? (
                        <><span className="banner-icon">🤝</span>
                          <span className="banner-text">It's a Tie! Both products score equally well.</span></>
                      ) : (
                        <><span className="banner-icon">🏆</span>
                          <span className="banner-text">
                            {comparison.winner === "flipkart" ? "Flipkart" : "Amazon"} wins with better overall value!
                          </span></>
                      )}
                    </div>
                  </div>
                )}

                {comparison.price_difference && (
                  <div className="price-diff-banner">
                    <span className="price-icon">💰</span>
                    <span className="price-text">
                      ₹{comparison.price_difference.amount.toLocaleString()} cheaper on{" "}
                      <strong>
                        {comparison.price_difference.cheaper_on === "flipkart" ? "Flipkart" : "Amazon"}
                      </strong>{" "}
                      ({comparison.price_difference.percentage}% savings)
                    </span>
                  </div>
                )}

                <div className="products-grid">
                  {comparison.flipkart && renderProductCard(comparison.flipkart, "flipkart")}
                  {comparison.amazon   && renderProductCard(comparison.amazon,   "amazon")}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── History Tab ──────────────────────────────────────────────────── */}
        {activeTab === "history" && (
          <div className="history-section">
            <h2 className="history-title">
              <span className="history-icon">📜</span>Comparison History
            </h2>

            {history.length === 0 ? (
              <div className="empty-history">
                <div className="empty-icon">📊</div>
                <div className="empty-text">No comparisons yet</div>
                <div className="empty-subtext">Start comparing products to build your history</div>
              </div>
            ) : (
              <div className="history-grid">
                {history.map(item => (
                  <div key={item.id} className="history-card">
                    <div className="history-header">
                      <span className="history-time">🕐 {item.timestamp}</span>
                      {item.winner && (
                        <span className={`history-winner ${item.winner}`}>
                          {item.winner === "tie" ? "🤝 Tie"
                            : `🏆 ${item.winner === "flipkart" ? "Flipkart" : "Amazon"}`}
                        </span>
                      )}
                    </div>
                    <div className="history-products">
                      {item.flipkart && (
                        <div className="history-product flipkart">
                          <div className="history-platform">🛒 Flipkart</div>
                          <div className="history-product-title">
                            {item.flipkart.title?.substring(0, 55)}…
                          </div>
                          <div className="history-details">
                            <span className="history-price">{item.flipkart.price}</span>
                            <span className="history-score">AI: {item.flipkart.ai_score}/100</span>
                          </div>
                        </div>
                      )}
                      {item.amazon && (
                        <div className="history-product amazon">
                          <div className="history-platform">📦 Amazon</div>
                          <div className="history-product-title">
                            {item.amazon.title?.substring(0, 55)}…
                          </div>
                          <div className="history-details">
                            <span className="history-price">{item.amazon.price}</span>
                            <span className="history-score">AI: {item.amazon.ai_score}/100</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Dashboard Tab ────────────────────────────────────────────────── */}
        {activeTab === "dashboard" && (
          <div className="dashboard-section">
            <h2 className="dashboard-title">
              <span className="dashboard-icon">📊</span>Analytics Dashboard
            </h2>

            {!dashboardData ? (
              <div className="dashboard-loading">
                <div className="loading-spinner"></div>
                <div>Loading dashboard…</div>
              </div>
            ) : (
              <div className="dashboard-content">
                <div className="stats-grid">
                  {[
                    { icon: "🔍", value: history.length,
                      label: "Total Comparisons" },
                    { icon: "🛒", value: history.filter(h => h.winner === "flipkart").length,
                      label: "Flipkart Wins" },
                    { icon: "📦", value: history.filter(h => h.winner === "amazon").length,
                      label: "Amazon Wins" },
                    { icon: "💰",
                      value: `₹${history.reduce((s, h) => s + (h.price_difference?.amount || 0), 0).toLocaleString()}`,
                      label: "Total Savings Found" },
                  ].map((s, i) => (
                    <div key={i} className="stat-card">
                      <div className="stat-icon">{s.icon}</div>
                      <div className="stat-value">{s.value}</div>
                      <div className="stat-label">{s.label}</div>
                    </div>
                  ))}
                </div>

                <div className="recent-activity">
                  <h3 className="section-title">📈 Recent Activity</h3>
                  {history.length === 0 ? (
                    <div className="empty-history" style={{ padding: "2rem" }}>
                      <div className="empty-text">No activity yet</div>
                    </div>
                  ) : (
                    <div className="activity-list">
                      {history.slice(0, 5).map(item => (
                        <div key={item.id} className="activity-item">
                          <div className="activity-time">{item.timestamp}</div>
                          <div className="activity-desc">
                            Compared{" "}
                            {item.flipkart && item.amazon
                              ? "Flipkart vs Amazon"
                              : item.flipkart ? "Flipkart product" : "Amazon product"}
                          </div>
                          {item.winner && item.winner !== "tie" && (
                            <div className="activity-winner">
                              🏆 {item.winner === "flipkart" ? "Flipkart" : "Amazon"} won
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Styles ────────────────────────────────────────────────────────── */}
      <style>{`
        *{margin:0;padding:0;box-sizing:border-box}

        .pricehawk-app{
          min-height:100vh;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Inter',sans-serif;
          position:relative;overflow-x:hidden
        }

        /* Background */
        .animated-bg{position:fixed;top:0;left:0;right:0;bottom:0;z-index:0}
        .bg-gradient{position:absolute;inset:0;background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#0f172a 100%)}
        .bg-circles{position:absolute;inset:0;overflow:hidden}
        .circle{position:absolute;border-radius:50%;filter:blur(80px);opacity:.3;animation:float 20s infinite ease-in-out}
        .circle-1{width:500px;height:500px;background:linear-gradient(135deg,#6366f1,#8b5cf6);top:-250px;left:-250px}
        .circle-2{width:400px;height:400px;background:linear-gradient(135deg,#ec4899,#f43f5e);bottom:-200px;right:-200px;animation-delay:7s}
        .circle-3{width:350px;height:350px;background:linear-gradient(135deg,#06b6d4,#3b82f6);top:50%;left:50%;animation-delay:14s}
        @keyframes float{0%,100%{transform:translate(0,0) scale(1)}25%{transform:translate(50px,-50px) scale(1.1)}50%{transform:translate(-30px,30px) scale(.9)}75%{transform:translate(40px,20px) scale(1.05)}}

        .app-content{position:relative;z-index:1;padding:2rem;max-width:1800px;margin:0 auto}

        /* Header */
        .app-header{text-align:center;margin-bottom:3rem;animation:fadeInDown .8s ease-out}
        @keyframes fadeInDown{from{opacity:0;transform:translateY(-30px)}to{opacity:1;transform:translateY(0)}}
        .logo-container{display:flex;align-items:center;justify-content:center;gap:1rem;margin-bottom:.5rem}
        .logo-icon{font-size:3.5rem;animation:bounce 2s infinite}
        @keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
        .logo-text{font-size:4rem;font-weight:900;letter-spacing:-2px;display:flex;gap:.3rem}
        .logo-price{background:linear-gradient(135deg,#60a5fa,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .logo-hawk{background:linear-gradient(135deg,#a78bfa,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .logo-pro{background:linear-gradient(135deg,#ec4899,#f43f5e);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2.5rem;align-self:flex-start}
        .tagline{font-size:1.25rem;color:#94a3b8;margin-bottom:2rem}

        /* Tabs */
        .tabs{display:flex;gap:1rem;justify-content:center}
        .tab{display:flex;align-items:center;gap:.5rem;padding:.75rem 1.5rem;border:2px solid rgba(255,255,255,.1);background:rgba(255,255,255,.05);color:#94a3b8;border-radius:12px;cursor:pointer;font-size:1rem;font-weight:600;transition:all .3s ease;position:relative}
        .tab:hover{border-color:#6366f1;transform:translateY(-2px)}
        .tab.active{background:linear-gradient(135deg,#6366f1,#8b5cf6);border-color:transparent;color:#fff;box-shadow:0 8px 20px rgba(99,102,241,.4)}
        .tab-icon{font-size:1.25rem}
        .tab-badge{position:absolute;top:-8px;right:-8px;background:#ef4444;color:#fff;font-size:.75rem;padding:.25rem .5rem;border-radius:10px;font-weight:700}

        /* Input Section */
        .input-section{background:rgba(255,255,255,.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.1);border-radius:24px;padding:2.5rem;margin-bottom:2rem;animation:fadeInUp .8s ease-out .2s both}
        @keyframes fadeInUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
        .input-group{margin-bottom:1.5rem}
        .input-label{display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem;font-weight:600;font-size:1rem}
        .label-icon{font-size:1.5rem}
        .label-text{color:#fff}
        .url-input{width:100%;padding:1rem 1.5rem;border-radius:12px;border:2px solid rgba(255,255,255,.1);background:rgba(255,255,255,.05);color:#fff;font-size:1rem;transition:all .3s ease}
        .url-input:focus{outline:none;background:rgba(255,255,255,.08);box-shadow:0 0 0 3px rgba(99,102,241,.1)}
        .url-input::placeholder{color:#64748b}
        .flipkart-input:focus{border-color:#2874f0;box-shadow:0 0 0 3px rgba(40,116,240,.1)}
        .amazon-input:focus{border-color:#ff9900;box-shadow:0 0 0 3px rgba(255,153,0,.1)}
        .input-divider{text-align:center;margin:1.5rem 0;position:relative}
        .divider-text{background:rgba(15,23,42,.9);padding:.5rem 1rem;border-radius:20px;color:#94a3b8;font-size:.875rem;font-weight:600;position:relative;z-index:1}
        .input-divider::before{content:'';position:absolute;top:50%;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.1),transparent)}

        /* Button */
        .compare-button{width:100%;padding:1.25rem;border:none;border-radius:14px;background:linear-gradient(135deg,#6366f1,#8b5cf6,#ec4899);color:#fff;font-size:1.125rem;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.75rem;transition:all .3s ease;box-shadow:0 10px 25px rgba(99,102,241,.3)}
        .compare-button:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 15px 35px rgba(99,102,241,.4)}
        .compare-button:disabled{opacity:.7;cursor:not-allowed}
        .button-icon{font-size:1.5rem}
        .button-spinner{width:20px;height:20px;border:3px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite}
        @keyframes spin{to{transform:rotate(360deg)}}

        /* Error */
        .error-message{display:flex;align-items:center;gap:.75rem;padding:1rem 1.5rem;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:12px;color:#fca5a5;margin-bottom:1.5rem;animation:shake .5s ease-in-out}
        @keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-10px)}75%{transform:translateX(10px)}}
        .error-icon{font-size:1.5rem}

        /* Loading */
        .loading-container{padding:4rem 0;animation:fadeIn .3s ease-out}
        @keyframes fadeIn{from{opacity:0}to{opacity:1}}
        .loading-animation{text-align:center}
        .loading-hawk{font-size:5rem;margin-bottom:1.5rem;animation:soar 2s ease-in-out infinite}
        @keyframes soar{0%,100%{transform:translateY(0) rotate(0deg)}25%{transform:translateY(-20px) rotate(-5deg)}75%{transform:translateY(-10px) rotate(5deg)}}
        .loading-text{font-size:1.25rem;color:#93c5fd;margin-bottom:1.5rem;font-weight:600}
        .loading-bar{width:300px;height:4px;background:rgba(255,255,255,.1);border-radius:2px;margin:0 auto 1.5rem;overflow:hidden}
        .loading-progress{height:100%;background:linear-gradient(90deg,#6366f1,#8b5cf6,#ec4899);border-radius:2px;animation:progress 1.5s ease-in-out infinite}
        @keyframes progress{0%{width:0%;margin-left:0%}50%{width:50%;margin-left:25%}100%{width:0%;margin-left:100%}}
        .loading-steps{display:flex;gap:2rem;justify-content:center;color:#64748b;font-size:.875rem;font-weight:600}

        /* Results */
        .results-section{animation:fadeInUp .8s ease-out}
        .winner-banner{padding:1.5rem;border-radius:16px;margin-bottom:1.5rem;animation:slideInDown .6s ease-out}
        @keyframes slideInDown{from{opacity:0;transform:translateY(-20px)}to{opacity:1;transform:translateY(0)}}
        .winner-banner.flipkart{background:linear-gradient(135deg,#2874f0,#1a5cc5);box-shadow:0 10px 30px rgba(40,116,240,.3)}
        .winner-banner.amazon{background:linear-gradient(135deg,#ff9900,#e68a00);box-shadow:0 10px 30px rgba(255,153,0,.3)}
        .winner-banner.tie{background:linear-gradient(135deg,#f59e0b,#d97706);box-shadow:0 10px 30px rgba(245,158,11,.3)}
        .banner-content{display:flex;align-items:center;justify-content:center;gap:1rem;font-size:1.5rem;font-weight:700;color:#fff}
        .banner-icon{font-size:2rem;animation:pulse 2s ease-in-out infinite}
        @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
        .price-diff-banner{display:flex;align-items:center;justify-content:center;gap:.75rem;padding:1.25rem;background:linear-gradient(135deg,rgba(34,197,94,.15),rgba(22,163,74,.15));border:1px solid rgba(34,197,94,.3);border-radius:12px;margin-bottom:2rem}
        .price-icon{font-size:1.75rem}
        .price-text{font-size:1.125rem;color:#86efac;font-weight:600}

        /* Products Grid */
        .products-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(550px,1fr));gap:2rem;margin-top:2rem}

        /* Product Card */
        .product-card{background:rgba(255,255,255,.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.1);border-radius:24px;padding:2rem;position:relative;transition:all .4s ease;animation:scaleIn .6s ease-out}
        @keyframes scaleIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:scale(1)}}
        .product-card:hover{transform:translateY(-8px);box-shadow:0 20px 40px rgba(0,0,0,.3)}
        .winner-card{border-color:#22c55e;box-shadow:0 0 0 2px rgba(34,197,94,.2),0 20px 40px rgba(34,197,94,.2)}
        .winner-crown{position:absolute;top:-20px;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;z-index:10}
        .crown-icon{font-size:2.5rem;animation:wiggle 1s ease-in-out infinite}
        @keyframes wiggle{0%,100%{transform:rotate(-5deg)}50%{transform:rotate(5deg)}}
        .crown-text{background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;padding:.375rem 1rem;border-radius:12px;font-size:.875rem;font-weight:700;box-shadow:0 4px 15px rgba(34,197,94,.4);margin-top:.5rem}
        .platform-badge{display:inline-flex;align-items:center;gap:.5rem;padding:.625rem 1.25rem;border-radius:20px;font-weight:700;font-size:.875rem;color:#fff;margin-bottom:1.5rem;box-shadow:0 4px 12px rgba(0,0,0,.2)}
        .platform-icon{font-size:1.25rem}

        /* Product Image */
        .product-image-container{position:relative;text-align:center;margin-bottom:1.5rem;padding:2rem 0}
        .image-glow{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:200px;height:200px;border-radius:50%;filter:blur(60px);opacity:.2;animation:glow-pulse 3s ease-in-out infinite}
        @keyframes glow-pulse{0%,100%{opacity:.2;transform:translate(-50%,-50%) scale(1)}50%{opacity:.4;transform:translate(-50%,-50%) scale(1.1)}}
        .product-image{position:relative;max-width:100%;max-height:300px;object-fit:contain;filter:drop-shadow(0 10px 30px rgba(0,0,0,.3));transition:transform .3s ease}
        .product-image:hover{transform:scale(1.05)}

        /* Product Info */
        .product-info{color:#fff}
        .product-title{font-size:1.25rem;line-height:1.4;margin-bottom:1.5rem;font-weight:600}
        .price-section{margin-bottom:1.5rem}
        .price-label{font-size:.875rem;color:#94a3b8;margin-bottom:.5rem}
        .price-value{font-size:2.25rem;font-weight:800;background:linear-gradient(135deg,#22c55e,#16a34a);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .rating-section{display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem}
        .stars-container{display:flex;gap:.25rem}
        .star{font-size:1.5rem;transition:transform .2s ease}
        .star.filled{color:#facc15}
        .star.half{color:#facc15}
        .star.empty{color:#475569}
        .rating-value{font-size:1.125rem;font-weight:700;color:#facc15}

        /* AI Score */
        .ai-score-section{background:linear-gradient(135deg,rgba(99,102,241,.1),rgba(139,92,246,.1));border:1px solid rgba(99,102,241,.2);border-radius:16px;padding:1.5rem;margin-bottom:1.5rem}
        .ai-score-header{display:flex;align-items:center;gap:.75rem;margin-bottom:1.5rem}
        .ai-icon{font-size:1.75rem}
        .ai-label{font-size:1.125rem;font-weight:700;color:#a78bfa}
        .score-circle-container{display:flex;justify-content:center;margin-bottom:1.5rem}
        .score-circle{width:140px;height:140px}
        .score-circle-bg{fill:none;stroke:rgba(255,255,255,.1);stroke-width:8}
        .score-circle-progress{fill:none;stroke-width:8;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center;transition:stroke-dasharray 1s ease-out;animation:drawCircle 1.5s ease-out}
        @keyframes drawCircle{from{stroke-dasharray:0 314}}
        .score-text{font-size:2.5rem;font-weight:800;fill:#fff;text-anchor:middle}
        .score-subtext{font-size:1rem;fill:#94a3b8;text-anchor:middle}
        .ai-verdict{text-align:center;font-size:1.375rem;font-weight:700;margin-bottom:1.25rem}
        .ai-reasons{display:flex;flex-direction:column;gap:.75rem;margin-bottom:1.25rem}
        .reason-item{display:flex;align-items:flex-start;gap:.75rem;padding:.75rem;background:rgba(255,255,255,.05);border-radius:10px;font-size:.9375rem;line-height:1.5}
        .reason-icon{color:#22c55e;font-weight:700;font-size:1.125rem;flex-shrink:0}
        .score-breakdown{background:rgba(0,0,0,.2);border-radius:12px;padding:1rem}
        .breakdown-title{font-size:.875rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:1rem;font-weight:600}
        .breakdown-bars{display:flex;flex-direction:column;gap:.75rem}
        .breakdown-label{display:flex;justify-content:space-between;font-size:.875rem;margin-bottom:.5rem;font-weight:600}
        .breakdown-bar{height:8px;background:rgba(255,255,255,.1);border-radius:4px;overflow:hidden}
        .breakdown-fill{height:100%;background:linear-gradient(90deg,#6366f1,#8b5cf6);border-radius:4px;transition:width 1s ease-out;animation:fillBar 1s ease-out}
        @keyframes fillBar{from{width:0%}}

        /* Specs */
        .specs-section{background:rgba(255,255,255,.03);border-radius:12px;padding:1.25rem;margin-bottom:1.5rem}
        .specs-title{font-size:1rem;font-weight:700;margin-bottom:1rem;color:#e2e8f0}
        .specs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:1rem}
        .spec-item{display:flex;align-items:center;gap:.625rem;padding:.75rem;background:rgba(255,255,255,.05);border-radius:10px;transition:transform .2s ease}
        .spec-item:hover{transform:translateY(-2px);background:rgba(255,255,255,.08)}
        .spec-icon{font-size:1.5rem}
        .spec-content{flex:1;min-width:0}
        .spec-label{font-size:.75rem;color:#94a3b8;margin-bottom:.25rem}
        .spec-value{font-size:.875rem;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

        /* Category Ratings */
        .category-section{background:rgba(255,255,255,.03);border-radius:12px;padding:1.25rem;margin-bottom:1.5rem}
        .category-title{font-size:1rem;font-weight:700;margin-bottom:1rem;color:#e2e8f0}
        .category-ratings{display:flex;flex-direction:column;gap:1rem}
        .category-header{display:flex;justify-content:space-between;margin-bottom:.5rem;font-size:.9375rem}
        .category-name{font-weight:600}
        .category-score{color:#facc15;font-weight:700}
        .category-bar{height:10px;background:rgba(255,255,255,.1);border-radius:5px;overflow:hidden}
        .category-fill{height:100%;background:linear-gradient(90deg,#facc15,#f59e0b);border-radius:5px;transition:width 1s ease-out;animation:fillBar 1s ease-out}

        /* Reviews */
        .reviews-section{background:rgba(255,255,255,.03);border-radius:12px;padding:1.25rem;margin-top:1.5rem}
        .reviews-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}
        .reviews-title{font-size:1rem;font-weight:700;color:#e2e8f0}
        .reviews-toggle{padding:.5rem 1rem;border-radius:8px;border:1px solid rgba(99,102,241,.3);background:rgba(99,102,241,.1);color:#a78bfa;font-size:.875rem;font-weight:600;cursor:pointer;transition:all .3s ease}
        .reviews-toggle:hover{background:rgba(99,102,241,.2);border-color:#6366f1}
        .reviews-list{display:flex;flex-direction:column;gap:1rem}
        .review-card{padding:1rem;background:rgba(255,255,255,.05);border-radius:10px;border:1px solid rgba(255,255,255,.1);transition:all .3s ease}
        .review-card:hover{background:rgba(255,255,255,.08);border-color:rgba(99,102,241,.3)}
        .review-header{display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem}
        .review-rating-num{font-size:.875rem;font-weight:700;color:#facc15}
        .review-text{font-size:.9375rem;line-height:1.6;color:#e2e8f0}

        /* History */
        .history-section{animation:fadeInUp .8s ease-out}
        .history-title{display:flex;align-items:center;gap:1rem;font-size:2rem;font-weight:700;color:#fff;margin-bottom:2rem}
        .history-icon{font-size:2.5rem}
        .empty-history{text-align:center;padding:4rem 2rem;color:#64748b}
        .empty-icon{font-size:5rem;margin-bottom:1.5rem;opacity:.5}
        .empty-text{font-size:1.5rem;font-weight:600;margin-bottom:.5rem}
        .empty-subtext{font-size:1rem}
        .history-grid{display:grid;gap:1.5rem}
        .history-card{background:rgba(255,255,255,.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:1.5rem;transition:transform .3s ease}
        .history-card:hover{transform:translateX(5px);border-color:rgba(99,102,241,.3)}
        .history-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem;padding-bottom:1rem;border-bottom:1px solid rgba(255,255,255,.1)}
        .history-time{font-size:.875rem;color:#94a3b8}
        .history-winner{padding:.375rem .875rem;border-radius:12px;font-size:.875rem;font-weight:700}
        .history-winner.flipkart{background:linear-gradient(135deg,#2874f0,#1a5cc5);color:#fff}
        .history-winner.amazon{background:linear-gradient(135deg,#ff9900,#e68a00);color:#fff}
        .history-winner.tie{background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff}
        .history-products{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}
        .history-product{padding:1rem;border-radius:12px;border:1px solid rgba(255,255,255,.1)}
        .history-product.flipkart{background:rgba(40,116,240,.1);border-color:rgba(40,116,240,.3)}
        .history-product.amazon{background:rgba(255,153,0,.1);border-color:rgba(255,153,0,.3)}
        .history-platform{font-size:.875rem;font-weight:700;color:#94a3b8;margin-bottom:.5rem}
        .history-product-title{font-size:.9375rem;color:#fff;margin-bottom:.75rem;line-height:1.4}
        .history-details{display:flex;justify-content:space-between;align-items:center}
        .history-price{font-size:1.125rem;font-weight:700;color:#22c55e}
        .history-score{font-size:.875rem;padding:.25rem .625rem;background:rgba(99,102,241,.2);border-radius:8px;font-weight:600;color:#a78bfa}

        /* Dashboard */
        .dashboard-section{animation:fadeInUp .8s ease-out}
        .dashboard-title{display:flex;align-items:center;gap:1rem;font-size:2rem;font-weight:700;color:#fff;margin-bottom:2rem}
        .dashboard-icon{font-size:2.5rem}
        .dashboard-loading{text-align:center;padding:4rem;color:#94a3b8}
        .loading-spinner{width:50px;height:50px;border:4px solid rgba(99,102,241,.2);border-top-color:#6366f1;border-radius:50%;margin:0 auto 1.5rem;animation:spin .8s linear infinite}
        .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1.5rem;margin-bottom:2rem}
        .stat-card{background:linear-gradient(135deg,rgba(99,102,241,.1),rgba(139,92,246,.1));border:1px solid rgba(99,102,241,.2);border-radius:16px;padding:2rem;text-align:center;transition:all .3s ease}
        .stat-card:hover{transform:translateY(-5px);box-shadow:0 10px 30px rgba(99,102,241,.3)}
        .stat-icon{font-size:3rem;margin-bottom:1rem}
        .stat-value{font-size:2.5rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.5rem}
        .stat-label{font-size:1rem;color:#94a3b8;font-weight:600}
        .recent-activity{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:2rem}
        .section-title{font-size:1.5rem;font-weight:700;color:#fff;margin-bottom:1.5rem}
        .activity-list{display:flex;flex-direction:column;gap:1rem}
        .activity-item{padding:1rem;background:rgba(255,255,255,.05);border-radius:10px;border-left:3px solid #6366f1}
        .activity-time{font-size:.875rem;color:#94a3b8;margin-bottom:.5rem}
        .activity-desc{font-size:1rem;color:#fff;margin-bottom:.25rem}
        .activity-winner{font-size:.875rem;color:#22c55e;font-weight:600}

        /* Responsive */
        @media(max-width:768px){
          .logo-text{font-size:2.5rem}
          .logo-pro{font-size:1.5rem}
          .products-grid{grid-template-columns:1fr}
          .input-section{padding:1.5rem}
          .stats-grid{grid-template-columns:1fr}
          .loading-steps{flex-direction:column;gap:.5rem}
        }
      `}</style>
    </div>
  );
}