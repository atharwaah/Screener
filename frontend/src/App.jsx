import { useEffect, useMemo, useState } from "react";
import TradingChart from "./TradingChart";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function normalizeSymbol(raw) {
  const trimmed = String(raw || "").trim().toUpperCase();
  if (!trimmed) return "";
  return trimmed.endsWith(".NS") ? trimmed : `${trimmed}.NS`;
}

function StatCard({ label, value, accent }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong className={accent ? "accent" : ""}>{value}</strong>
    </div>
  );
}

function SortHeader({ label, sortKey, sort, onSort }) {
  const active = sort.key === sortKey;
  return (
    <th
      className={`sortable${active ? " sorted" : ""}`}
      onClick={() => onSort(sortKey)}
    >
      {label}
      <span className="sort-arrow">
        {active ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
      </span>
    </th>
  );
}

function sortRows(rows, sort) {
  if (!sort.key) return rows;

  const copy = [...rows];

  copy.sort((a, b) => {
    const av = a[sort.key];
    const bv = b[sort.key];

    let cmp;
    if (typeof av === "string" || typeof bv === "string") {
      cmp = String(av ?? "").localeCompare(String(bv ?? ""));
    } else {
      cmp = (Number(av) || 0) - (Number(bv) || 0);
    }

    return sort.dir === "asc" ? cmp : -cmp;
  });

  return copy;
}

function App() {
  const [activeTab, setActiveTab] = useState("watchlist");

  const [watchlistData, setWatchlistData] = useState(null);
  const [newHighData, setNewHighData] = useState(null);

  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [loadingNewHigh, setLoadingNewHigh] = useState(false);

  const [error, setError] = useState("");

  const [selectedStock, setSelectedStock] = useState(null);
  const [chartTimeframe, setChartTimeframe] = useState("1d");
  const [chartData, setChartData] = useState(null);
  const [chartIssue, setChartIssue] = useState(null); // graceful, in-modal message
  const [loadingChart, setLoadingChart] = useState(false);

  // Screener controls
  const [nearResistancePercent, setNearResistancePercent] = useState(10);
  const [pendingPercent, setPendingPercent] = useState(10);
  const [includeNewListings, setIncludeNewListings] = useState(true);

  const [watchlistSearch, setWatchlistSearch] = useState("");
  const [newHighSearch, setNewHighSearch] = useState("");

  const [watchlistSort, setWatchlistSort] = useState({
    key: "distance_percent",
    dir: "asc",
  });
  const [newHighSort, setNewHighSort] = useState({
    key: "breakout_percent",
    dir: "desc",
  });

  const [lookupSymbol, setLookupSymbol] = useState("");
  const [lookupBusy, setLookupBusy] = useState(false);

  // Paper trading
  const [portfolio, setPortfolio] = useState(null);
  const [loadingPortfolio, setLoadingPortfolio] = useState(false);
  const [trades, setTrades] = useState([]);
  const [tradeQty, setTradeQty] = useState(1);
  const [tradeBusy, setTradeBusy] = useState(false);
  const [tradeMessage, setTradeMessage] = useState(null); // { type: "ok"|"error", text }

  /* ----------------------------- Weekly resistance scanner ----------------------------- */
  const scanWatchlist = async (
    forceRefresh = false,
    percent = nearResistancePercent
  ) => {
    try {
      setLoadingWatchlist(true);
      setError("");

      const response = await fetch(
        `${API_BASE}/api/scan-nifty500?timeframe=1wk&near_resistance_percent=${percent}&force_refresh=${forceRefresh}`
      );

      if (!response.ok) {
        throw new Error("Failed to load resistance watchlist");
      }

      const data = await response.json();
      setWatchlistData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingWatchlist(false);
    }
  };

  /* ----------------------------- New 52W high scanner ----------------------------- */
  const scanNewHighs = async (forceRefresh = false) => {
    try {
      setLoadingNewHigh(true);
      setError("");

      const response = await fetch(
        `${API_BASE}/api/scan-nifty500-new-highs?force_refresh=${forceRefresh}`
      );

      if (!response.ok) {
        throw new Error("Failed to load new 52-week highs");
      }

      const data = await response.json();
      setNewHighData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingNewHigh(false);
    }
  };

  /* ----------------------------- Chart loader ----------------------------- */
  const openChart = async (symbol, timeframe = "1d") => {
    setSelectedStock(symbol);
    setChartTimeframe(timeframe);
    setChartData(null);
    setChartIssue(null);
    setLoadingChart(true);

    try {
      const response = await fetch(
        `${API_BASE}/api/stock/${encodeURIComponent(symbol)}/${timeframe}`
      );

      if (!response.ok) {
        throw new Error(`Failed to load ${timeframe} data for ${symbol}`);
      }

      const data = await response.json();

      if (!data) {
        throw new Error(`No response for ${symbol} (${timeframe})`);
      }

      // Backend statuses that don't come with a chart: show a friendly
      // in-modal explanation instead of a hard error / blank screen.
      if (data.status === "NO_DATA") {
        setChartIssue({
          title: "No data available",
          detail: `Couldn't fetch ${timeframe === "1wk" ? "weekly" : "daily"} price data for ${symbol.replace(".NS", "")}. It may be delisted, suspended, or an invalid symbol.`,
        });
        return;
      }

      if (data.status === "INSUFFICIENT_HISTORY") {
        const have = data.available_candles ?? 0;
        const need = data.min_candles_required ?? "more";
        setChartIssue({
          title: "Not enough trading history yet",
          detail: `${symbol.replace(".NS", "")} only has ${have} ${
            timeframe === "1wk" ? "weekly" : "daily"
          } candles so far (needs ~${need}). This usually means it's a recently listed stock. ${
            timeframe === "1wk"
              ? "Try the Daily timeframe, which needs less history."
              : ""
          }`,
        });
        return;
      }

      if (!Array.isArray(data.chart) || !data.chart.length) {
        setChartIssue({
          title: "No chart data",
          detail: `The server didn't return any candles for ${symbol} (${timeframe}).`,
        });
        return;
      }

      setChartData(data);
    } catch (err) {
      setChartIssue({
        title: "Something went wrong",
        detail: err.message,
      });
    } finally {
      setLoadingChart(false);
    }
  };

  const closeChart = () => {
    setSelectedStock(null);
    setChartData(null);
    setChartIssue(null);
    setLoadingChart(false);
    setTradeQty(1);
    setTradeMessage(null);
  };

  /* ----------------------------- Paper trading ----------------------------- */
  const loadPortfolio = async () => {
    try {
      setLoadingPortfolio(true);
      const response = await fetch(`${API_BASE}/api/paper/portfolio`);
      if (!response.ok) throw new Error("Failed to load paper portfolio");
      const data = await response.json();
      setPortfolio(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingPortfolio(false);
    }
  };

  const loadTrades = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/paper/trades`);
      if (!response.ok) throw new Error("Failed to load trade history");
      const data = await response.json();
      setTrades(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const placeOrder = async (side, symbol, quantity) => {
    setTradeBusy(true);
    setTradeMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/paper/${side}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, quantity: Number(quantity) }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Failed to ${side}`);
      }

      setTradeMessage({
        type: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${data.quantity} ${symbol.replace(
          ".NS",
          ""
        )} @ ₹${data.price.toFixed(2)}`,
      });

      await Promise.all([loadPortfolio(), loadTrades()]);
    } catch (err) {
      setTradeMessage({ type: "error", text: err.message });
    } finally {
      setTradeBusy(false);
    }
  };

  const resetPaperAccount = async () => {
    if (!window.confirm("Reset paper account? This clears all positions and trade history.")) {
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/paper/reset`, { method: "POST" });
      if (!response.ok) throw new Error("Failed to reset paper account");
      await Promise.all([loadPortfolio(), loadTrades()]);
    } catch (err) {
      setError(err.message);
    }
  };

  const runQuickLookup = (event) => {
    event.preventDefault();
    const symbol = normalizeSymbol(lookupSymbol);
    if (!symbol) return;

    setLookupBusy(true);
    openChart(symbol, "1d").finally(() => setLookupBusy(false));
  };

  /* ----------------------------- Esc closes modal ----------------------------- */
  useEffect(() => {
    if (!selectedStock) return;

    const onKey = (event) => {
      if (event.key === "Escape") closeChart();
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedStock]);

  /* ----------------------------- Initial scans ----------------------------- */
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    scanWatchlist(false, nearResistancePercent);
    scanNewHighs();
    loadPortfolio();
    loadTrades();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === "portfolio") {
      loadPortfolio();
      loadTrades();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Keep open-position LTP and P&L refreshed while the portfolio is visible.
  // The backend bypasses the scanner cache for these portfolio price reads.
  useEffect(() => {
    if (activeTab !== "portfolio") return;

    const intervalId = window.setInterval(() => {
      loadPortfolio();
    }, 60000);

    return () => window.clearInterval(intervalId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Current holding for whichever stock is open in the chart modal
  const selectedPosition = useMemo(() => {
    if (!selectedStock || !portfolio) return null;
    return (
      portfolio.positions.find((p) => p.symbol === selectedStock) || null
    );
  }, [selectedStock, portfolio]);

  const applyPercent = () => {
    const clamped = Math.min(50, Math.max(0, Number(pendingPercent) || 0));
    setNearResistancePercent(clamped);
    setPendingPercent(clamped);
    scanWatchlist(false, clamped);
  };

  /* ----------------------------- Derived rows ----------------------------- */
  const watchlistBase = useMemo(() => {
    if (!watchlistData) return [];
    return includeNewListings
      ? watchlistData.watchlist || []
      : watchlistData.watchlist_established || [];
  }, [watchlistData, includeNewListings]);

  const watchlist = useMemo(() => {
    const filtered = watchlistSearch
      ? watchlistBase.filter((s) =>
          s.symbol.toLowerCase().includes(watchlistSearch.toLowerCase())
        )
      : watchlistBase;
    return sortRows(filtered, watchlistSort);
  }, [watchlistBase, watchlistSearch, watchlistSort]);

  const newHighsBase = useMemo(() => {
    if (!newHighData) return [];
    return includeNewListings
      ? newHighData.new_52w_high || []
      : newHighData.new_52w_high_established || [];
  }, [newHighData, includeNewListings]);

  const newHighs = useMemo(() => {
    const filtered = newHighSearch
      ? newHighsBase.filter((s) =>
          s.symbol.toLowerCase().includes(newHighSearch.toLowerCase())
        )
      : newHighsBase;
    return sortRows(filtered, newHighSort);
  }, [newHighsBase, newHighSearch, newHighSort]);

  const toggleWatchlistSort = (key) => {
    setWatchlistSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" }
    );
  };

  const toggleNewHighSort = (key) => {
    setNewHighSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" }
    );
  };

  return (
    <div className="app">
      {/* -------------------------------- TOP BAR -------------------------------- */}
      <header className="topbar">
        <div>
          <div className="brand">
            <div className="brand-mark">52</div>
            <div>
              <h1>NIFTY 500 Scanner</h1>
              <p>Resistance watchlist · New 52W highs</p>
            </div>
          </div>
        </div>

        <form className="quick-lookup" onSubmit={runQuickLookup}>
          <input
            type="text"
            placeholder="Quick lookup e.g. TATAMOTORS"
            value={lookupSymbol}
            onChange={(e) => setLookupSymbol(e.target.value)}
          />
          <button type="submit" disabled={lookupBusy || !lookupSymbol.trim()}>
            {lookupBusy ? "…" : "Chart"}
          </button>
        </form>

        <div className="topbar-status">
          <span className="status-dot" />
          Market Scanner
        </div>
      </header>

      <main className="main">
        {error && <div className="error-message">{error}</div>}

        {/* -------------------------------- TABS -------------------------------- */}
        <div className="tabs">
          <button
            className={activeTab === "watchlist" ? "tab active" : "tab"}
            onClick={() => setActiveTab("watchlist")}
          >
            <span>52W Resistance</span>
            <small>{watchlist.length}</small>
          </button>

          <button
            className={activeTab === "newhigh" ? "tab active" : "tab"}
            onClick={() => setActiveTab("newhigh")}
          >
            <span>New 52W High</span>
            <small>{newHighs.length}</small>
          </button>

          <button
            className={activeTab === "portfolio" ? "tab active" : "tab"}
            onClick={() => setActiveTab("portfolio")}
          >
            <span>Paper Portfolio</span>
            <small>{portfolio ? `₹${Math.round(portfolio.total_value).toLocaleString("en-IN")}` : "-"}</small>
          </button>
        </div>

        {/* Shared "new listings" toggle, applies to both scanner tabs */}
        {activeTab !== "portfolio" && (
          <label className="listing-toggle">
            <input
              type="checkbox"
              checked={includeNewListings}
              onChange={(e) => setIncludeNewListings(e.target.checked)}
            />
            Include recently listed stocks (partial history, flagged separately)
          </label>
        )}

        {/* ================================= WATCHLIST TAB ================================= */}
        {activeTab === "watchlist" && (
          <>
            <section className="stats-grid">
              <StatCard label="Universe" value={watchlistData?.total_stocks ?? "-"} />
              <StatCard
                label="Watchlist"
                value={watchlistData?.watchlist_count ?? "-"}
                accent
              />
              <StatCard
                label="New Listings in Watchlist"
                value={watchlistData?.watchlist_new_listings_count ?? "-"}
              />
              <StatCard
                label="Insufficient History"
                value={watchlistData?.insufficient_history_count ?? "-"}
              />
              <StatCard label="No Data" value={watchlistData?.no_data_count ?? "-"} />
            </section>

            <section className="scanner-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">WEEKLY SCANNER</div>
                  <h2>Resistance Watchlist</h2>
                  <p>
                    Price is within {nearResistancePercent}% of the previous
                    52-week resistance and above the 200-week MA (best-available
                    MA for recently listed stocks).
                  </p>
                </div>

                <button
                  className="refresh-button"
                  onClick={() => scanWatchlist(true)}
                  disabled={loadingWatchlist}
                >
                  {loadingWatchlist ? "Scanning..." : "Refresh"}
                </button>
              </div>

              <div className="panel-toolbar">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search symbol..."
                  value={watchlistSearch}
                  onChange={(e) => setWatchlistSearch(e.target.value)}
                />

                <div className="percent-control">
                  <label htmlFor="near-pct">Within</label>
                  <input
                    id="near-pct"
                    type="number"
                    min="0"
                    max="50"
                    step="0.5"
                    value={pendingPercent}
                    onChange={(e) => setPendingPercent(e.target.value)}
                  />
                  <span>% of resistance</span>
                  <button
                    className="apply-button"
                    onClick={applyPercent}
                    disabled={loadingWatchlist}
                  >
                    Apply
                  </button>
                </div>
              </div>

              {loadingWatchlist && !watchlistData ? (
                <div className="loading">
                  <span className="spinner" />
                  Scanning NIFTY 500... this can take a little while the first
                  time.
                </div>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Stock</th>
                        <SortHeader
                          label="Price"
                          sortKey="current_price"
                          sort={watchlistSort}
                          onSort={toggleWatchlistSort}
                        />
                        <SortHeader
                          label="52W Resistance"
                          sortKey="resistance_52w"
                          sort={watchlistSort}
                          onSort={toggleWatchlistSort}
                        />
                        <SortHeader
                          label="Distance"
                          sortKey="distance_percent"
                          sort={watchlistSort}
                          onSort={toggleWatchlistSort}
                        />
                        <SortHeader
                          label="200W MA"
                          sortKey="ma_200"
                          sort={watchlistSort}
                          onSort={toggleWatchlistSort}
                        />
                        <th />
                      </tr>
                    </thead>

                    <tbody>
                      {watchlist.map((stock) => (
                        <tr key={stock.symbol}>
                          <td>
                            <div className="stock-name">
                              {stock.symbol.replace(".NS", "")}
                            </div>
                            <div className="stock-sub">
                              NIFTY 500
                              {stock.is_recent_listing && (
                                <span
                                  className="listing-badge"
                                  title={`Using a ${stock.ma_period_used}-candle MA / ${stock.resistance_lookback_used}-candle resistance window (recently listed)`}
                                >
                                  New listing
                                </span>
                              )}
                            </div>
                          </td>

                          <td className="number">
                            ₹{Number(stock.current_price).toFixed(2)}
                          </td>

                          <td className="number">
                            ₹{Number(stock.resistance_52w).toFixed(2)}
                          </td>

                          <td>
                            <span className="distance-badge">
                              {Number(stock.distance_percent).toFixed(2)}%
                            </span>
                          </td>

                          <td className="number muted">
                            ₹{Number(stock.ma_200).toFixed(2)}
                          </td>

                          <td className="action-cell">
                            <button
                              className="chart-button"
                              onClick={() => openChart(stock.symbol, "1wk")}
                            >
                              Chart
                            </button>
                          </td>
                        </tr>
                      ))}

                      {!watchlist.length && (
                        <tr>
                          <td colSpan="6" className="empty">
                            {watchlistSearch
                              ? "No matching stocks."
                              : "No stocks currently qualify."}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        {/* ================================= NEW HIGH TAB ================================= */}
        {activeTab === "newhigh" && (
          <>
            <section className="stats-grid">
              <StatCard label="Universe" value={newHighData?.total_stocks ?? "-"} />
              <StatCard
                label="New 52W High"
                value={newHighData?.new_52w_high_count ?? "-"}
                accent
              />
              <StatCard
                label="New Listings"
                value={newHighData?.new_52w_high_new_listings_count ?? "-"}
              />
              <StatCard
                label="Insufficient History"
                value={newHighData?.insufficient_history_count ?? "-"}
              />
              <StatCard label="No Data" value={newHighData?.no_data_count ?? "-"} />
            </section>

            <section className="scanner-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">DAILY SCANNER</div>
                  <h2>New 52-Week Highs</h2>
                  <p>
                    Today's high is above the highest high of the previous
                    trading history (up to 252 days).
                  </p>
                </div>

                <button
                  className="refresh-button"
                  onClick={() => scanNewHighs(true)}
                  disabled={loadingNewHigh}
                >
                  {loadingNewHigh ? "Scanning..." : "Refresh"}
                </button>
              </div>

              {newHighData?.universe_note && (
                <div className="info-banner">{newHighData.universe_note}</div>
              )}

              <div className="panel-toolbar">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search symbol..."
                  value={newHighSearch}
                  onChange={(e) => setNewHighSearch(e.target.value)}
                />
              </div>

              {loadingNewHigh && !newHighData ? (
                <div className="loading">
                  <span className="spinner" />
                  Scanning NIFTY 500... this can take a little while the first
                  time.
                </div>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Stock</th>
                        <SortHeader
                          label="Price"
                          sortKey="current_price"
                          sort={newHighSort}
                          onSort={toggleNewHighSort}
                        />
                        <SortHeader
                          label="Today's High"
                          sortKey="current_high"
                          sort={newHighSort}
                          onSort={toggleNewHighSort}
                        />
                        <SortHeader
                          label="Previous 52W High"
                          sortKey="previous_52w_high"
                          sort={newHighSort}
                          onSort={toggleNewHighSort}
                        />
                        <th>Previous High</th>
                        <SortHeader
                          label="Breakout"
                          sortKey="breakout_percent"
                          sort={newHighSort}
                          onSort={toggleNewHighSort}
                        />
                        <th />
                      </tr>
                    </thead>

                    <tbody>
                      {newHighs.map((stock) => (
                        <tr key={stock.symbol}>
                          <td>
                            <div className="stock-name">
                              {stock.symbol.replace(".NS", "")}
                            </div>
                            <div className="stock-sub">
                              NIFTY 500
                              {stock.is_recent_listing && (
                                <span
                                  className="listing-badge"
                                  title={`Using a ${stock.lookback_used}-day lookback (recently listed)`}
                                >
                                  New listing
                                </span>
                              )}
                            </div>
                          </td>

                          <td className="number">
                            ₹{Number(stock.current_price).toFixed(2)}
                          </td>

                          <td className="number">
                            ₹{Number(stock.current_high).toFixed(2)}
                          </td>

                          <td className="number">
                            ₹{Number(stock.previous_52w_high).toFixed(2)}
                          </td>

                          <td className="muted">{stock.previous_high_date}</td>

                          <td>
                            <span className="breakout-badge">
                              +{Number(stock.breakout_percent).toFixed(2)}%
                            </span>
                          </td>

                          <td className="action-cell">
                            <button
                              className="chart-button"
                              onClick={() => openChart(stock.symbol, "1d")}
                            >
                              Chart
                            </button>
                          </td>
                        </tr>
                      ))}

                      {!newHighs.length && (
                        <tr>
                          <td colSpan="7" className="empty">
                            {newHighSearch
                              ? "No matching stocks."
                              : "No new 52-week highs detected."}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        {/* ================================= PORTFOLIO TAB ================================= */}
        {activeTab === "portfolio" && (
          <section className="scanner-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">PAPER TRADING</div>
                <h2>Simulated Portfolio</h2>
                <p>Test your strategy with fake money at real (last-close) prices.</p>
              </div>
              <button
                className="refresh-button"
                onClick={() => {
                  loadPortfolio();
                  loadTrades();
                }}
                disabled={loadingPortfolio}
              >
                {loadingPortfolio ? "Loading…" : "Refresh"}
              </button>
            </div>

            {loadingPortfolio && !portfolio && (
              <div className="loading">
                <span className="spinner" />
                Loading portfolio...
              </div>
            )}

            {portfolio && (
              <>
                <section className="stats-grid">
                  <StatCard label="Cash" value={`₹${portfolio.cash.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
                  <StatCard label="Positions Value" value={`₹${portfolio.positions_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
                  <StatCard label="Total Value" value={`₹${portfolio.total_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} accent />
                  <StatCard
                    label={`Total P&L (${portfolio.total_pnl_percent >= 0 ? "+" : ""}${portfolio.total_pnl_percent.toFixed(2)}%)`}
                    value={`${portfolio.total_pnl >= 0 ? "+" : ""}₹${portfolio.total_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
                    accent
                  />
                </section>

                <div className="panel-toolbar">
                  <span className="muted">Started with ₹{portfolio.initial_cash.toLocaleString("en-IN")}</span>
                  <button className="refresh-button" onClick={resetPaperAccount}>
                    Reset Account
                  </button>
                </div>

                <h3 style={{ margin: "20px 0 8px" }}>Open Positions</h3>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Symbol</th>
                        <th>Qty</th>
                        <th>Avg. Price</th>
                        <th>LTP</th>
                        <th>Market Value</th>
                        <th>Unrealized P&amp;L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.positions.map((position) => (
                        <tr
                          key={position.symbol}
                          className="clickable-row"
                          onClick={() => openChart(position.symbol, "1d")}
                        >
                          <td className="stock-name">{position.symbol.replace(".NS", "")}</td>
                          <td className="number">{position.quantity}</td>
                          <td className="number">₹{position.average_price.toFixed(2)}</td>
                          <td className="number">
                            {position.current_price != null ? `₹${position.current_price.toFixed(2)}` : "-"}
                          </td>
                          <td className="number">
                            {position.market_value != null ? `₹${position.market_value.toFixed(2)}` : "-"}
                          </td>
                          <td
                            className={`number ${
                              position.unrealized_pnl == null
                                ? ""
                                : position.unrealized_pnl >= 0
                                ? "positive"
                                : "negative"
                            }`}
                          >
                            {position.unrealized_pnl != null
                              ? `${position.unrealized_pnl >= 0 ? "+" : ""}₹${position.unrealized_pnl.toFixed(2)} (${position.unrealized_pnl_percent.toFixed(2)}%)`
                              : "-"}
                          </td>
                        </tr>
                      ))}

                      {!portfolio.positions.length && (
                        <tr>
                          <td colSpan="6" className="empty">
                            No open positions yet. Open a stock's chart and use Buy to get started.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <h3 style={{ margin: "20px 0 8px" }}>Trade History</h3>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Qty</th>
                        <th>Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((trade) => (
                        <tr key={trade.id}>
                          <td className="muted">{new Date(trade.timestamp).toLocaleString("en-IN")}</td>
                          <td className="stock-name">{trade.symbol.replace(".NS", "")}</td>
                          <td className={trade.side === "BUY" ? "positive" : "negative"}>{trade.side}</td>
                          <td className="number">{trade.quantity}</td>
                          <td className="number">₹{trade.price.toFixed(2)}</td>
                        </tr>
                      ))}

                      {!trades.length && (
                        <tr>
                          <td colSpan="5" className="empty">
                            No trades yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        )}
      </main>

      {/* ================================= CHART MODAL ================================= */}
      {selectedStock && (
        <div
          className="chart-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeChart();
          }}
        >
          <section className="chart-modal">
            {/* HEADER */}
            <div className="chart-modal-header">
              <div>
                <div className="eyebrow">
                  {chartTimeframe === "1d" ? "DAILY" : "WEEKLY"} CHART
                </div>
                <h2>{selectedStock.replace(".NS", "")}</h2>
                <p>Price action · 200 MA · 52W level</p>
              </div>

              <div className="chart-actions">
                <div className="timeframe-switch">
                  <button
                    className={chartTimeframe === "1d" ? "active" : ""}
                    onClick={() => openChart(selectedStock, "1d")}
                  >
                    Daily
                  </button>

                  <button
                    className={chartTimeframe === "1wk" ? "active" : ""}
                    onClick={() => openChart(selectedStock, "1wk")}
                  >
                    Weekly
                  </button>
                </div>

                <button className="close-button" onClick={closeChart}>
                  ×
                </button>
              </div>
            </div>

            {/* LOADING */}
            {loadingChart && (
              <div className="loading chart-loading">
                <span className="spinner" />
                Loading {chartTimeframe === "1wk" ? "weekly" : "daily"} chart...
              </div>
            )}

            {/* GRACEFUL IN-MODAL ISSUE (insufficient history / no data / etc.) */}
            {!loadingChart && chartIssue && (
              <div className="chart-issue">
                <h3>{chartIssue.title}</h3>
                <p>{chartIssue.detail}</p>
              </div>
            )}

            {/* CHART */}
            {!loadingChart &&
              chartData &&
              Array.isArray(chartData.chart) &&
              chartData.chart.length > 0 && (
                <>
                  <div className="chart-metrics">
                    <div className="chart-metric">
                      <span>Price</span>
                      <strong>₹{Number(chartData.current_price).toFixed(2)}</strong>
                    </div>

                    <div className="chart-metric">
                      <span>52W Level</span>
                      <strong>₹{Number(chartData.resistance_52w).toFixed(2)}</strong>
                    </div>

                    <div className="chart-metric">
                      <span>
                        MA
                        {chartData.ma_period_used
                          ? ` (${chartData.ma_period_used})`
                          : ""}
                      </span>
                      <strong>₹{Number(chartData.ma_200).toFixed(2)}</strong>
                    </div>

                    <div className="chart-metric">
                      <span>Distance</span>
                      <strong>{Number(chartData.distance_percent).toFixed(2)}%</strong>
                    </div>

                    <div className="chart-metric">
                      <span>Trend</span>
                      <strong
                        className={chartData.above_ma_200 ? "positive" : "negative"}
                      >
                        {chartData.above_ma_200 ? "Above MA" : "Below MA"}
                      </strong>
                    </div>
                  </div>

                  {chartData.is_recent_listing && (
                    <div className="info-banner subtle">
                      Recently listed stock — MA/resistance use the best
                      available history ({chartData.ma_period_used} candles)
                      rather than the full 200.
                    </div>
                  )}

                  {/* PAPER TRADING PANEL */}
                  <div className="trade-panel">
                    <div className="trade-panel-row">
                      <span className="muted">
                        {selectedPosition
                          ? `Holding: ${selectedPosition.quantity} @ ₹${selectedPosition.average_price.toFixed(2)} avg`
                          : "No position held"}
                      </span>
                      <span className="muted">
                        Cash: ₹{portfolio ? portfolio.cash.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : "-"}
                      </span>
                    </div>

                    <div className="trade-panel-row">
                      <input
                        type="number"
                        min="1"
                        step="1"
                        className="qty-input"
                        value={tradeQty}
                        onChange={(e) => setTradeQty(e.target.value)}
                      />

                      <button
                        className="trade-button buy"
                        disabled={tradeBusy || !tradeQty || Number(tradeQty) <= 0}
                        onClick={() => placeOrder("buy", selectedStock, tradeQty)}
                      >
                        {tradeBusy ? "…" : `Buy @ ₹${Number(chartData.current_price).toFixed(2)}`}
                      </button>

                      <button
                        className="trade-button sell"
                        disabled={
                          tradeBusy ||
                          !tradeQty ||
                          Number(tradeQty) <= 0 ||
                          !selectedPosition ||
                          Number(tradeQty) > selectedPosition.quantity
                        }
                        onClick={() => placeOrder("sell", selectedStock, tradeQty)}
                      >
                        {tradeBusy ? "…" : "Sell"}
                      </button>
                    </div>

                    {tradeMessage && (
                      <div className={`trade-message ${tradeMessage.type}`}>
                        {tradeMessage.text}
                      </div>
                    )}
                  </div>

                  <div className="chart-hint">
                    Scroll or pinch to zoom · click &amp; drag to pan
                  </div>

                  <div
                    className="chart-container"
                    style={{ width: "100%", minHeight: "520px", height: "520px" }}
                  >
                    <TradingChart
                      key={`${selectedStock}-${chartTimeframe}`}
                      data={chartData.chart}
                      maLabel={
                        chartData.ma_period_used
                          ? `${chartData.ma_period_used} MA`
                          : "200 MA"
                      }
                      resistanceLabel={
                        chartTimeframe === "1d" ? "52W High" : "52W Resistance"
                      }
                    />
                  </div>
                </>
              )}
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
