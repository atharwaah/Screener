import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  CrosshairMode,
} from "lightweight-charts";

/*
 * Fully interactive candlestick chart:
 *  - scroll wheel / pinch to zoom
 *  - click & drag to pan
 *  - crosshair with OHLC + MA + resistance tooltip
 *  - resizes with its container
 *
 * Built on lightweight-charts (already a project dependency),
 * replacing the old static, non-interactive hand-drawn SVG.
 */
function TradingChart({
  data,
  resistanceLabel = "52W Resistance",
  maLabel = "200 MA",
}) {
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const rows = (Array.isArray(data) ? data : [])
      .map((item) => {
        const date = String(item?.date || "").slice(0, 10);
        const open = Number(item?.open);
        const high = Number(item?.high);
        const low = Number(item?.low);
        const close = Number(item?.close);
        const volume = Number(item?.volume || 0);
        const ma200 =
          item?.ma200 === null || item?.ma200 === undefined
            ? null
            : Number(item.ma200);
        const resistance =
          item?.resistance === null || item?.resistance === undefined
            ? null
            : Number(item.resistance);

        if (
          !date ||
          !Number.isFinite(open) ||
          !Number.isFinite(high) ||
          !Number.isFinite(low) ||
          !Number.isFinite(close)
        ) {
          return null;
        }

        return {
          time: date,
          open,
          high,
          low,
          close,
          volume: Number.isFinite(volume) ? volume : 0,
          ma200: Number.isFinite(ma200) ? ma200 : null,
          resistance: Number.isFinite(resistance) ? resistance : null,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.time.localeCompare(b.time));

    // de-dupe by date, keep last
    const unique = [];
    for (const row of rows) {
      const prev = unique[unique.length - 1];
      if (prev && prev.time === row.time) {
        unique[unique.length - 1] = row;
      } else {
        unique.push(row);
      }
    }

    if (!unique.length) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "#1a2436" },
        horzLines: { color: "#1a2436" },
      },
      rightPriceScale: {
        borderColor: "#253044",
      },
      timeScale: {
        borderColor: "#253044",
        timeVisible: false,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      autoSize: true,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      priceScaleId: "right",
    });

    candleSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.28 },
    });

    candleSeries.setData(
      unique.map((row) => ({
        time: row.time,
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close,
      }))
    );

    // 200 (or best-available) MA line
    const maPoints = unique
      .filter((row) => row.ma200 !== null)
      .map((row) => ({ time: row.time, value: row.ma200 }));

    if (maPoints.length) {
      const maSeries = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 2,
        priceScaleId: "right",
        lastValueVisible: false,
        priceLineVisible: false,
        title: maLabel,
      });
      maSeries.setData(maPoints);
    }

    // Resistance level line
    const resistancePoints = unique
      .filter((row) => row.resistance !== null)
      .map((row) => ({ time: row.time, value: row.resistance }));

    if (resistancePoints.length) {
      const resistanceSeries = chart.addSeries(LineSeries, {
        color: "#ef4444",
        lineWidth: 1,
        lineStyle: 2, // dashed
        priceScaleId: "right",
        lastValueVisible: false,
        priceLineVisible: false,
        title: resistanceLabel,
      });
      resistanceSeries.setData(resistancePoints);
    }

    // Volume histogram in its own scale at the bottom
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    volumeSeries.setData(
      unique.map((row) => ({
        time: row.time,
        value: row.volume,
        color:
          row.close >= row.open
            ? "rgba(34,197,94,0.5)"
            : "rgba(239,68,68,0.5)",
      }))
    );

    chart.timeScale().fitContent();

    // Custom tooltip on crosshair move
    const tooltipEl = tooltipRef.current;

    const handleCrosshairMove = (param) => {
      if (!tooltipEl) return;

      if (
        !param.time ||
        !param.point ||
        param.point.x < 0 ||
        param.point.y < 0
      ) {
        tooltipEl.style.display = "none";
        return;
      }

      const candle = param.seriesData.get(candleSeries);

      if (!candle) {
        tooltipEl.style.display = "none";
        return;
      }

      tooltipEl.style.display = "block";

      const row = unique.find((r) => r.time === param.time);

      const lines = [
        `<div class="tt-date">${param.time}</div>`,
        `<div class="tt-row"><span>O</span>${candle.open.toFixed(
          2
        )} <span>H</span>${candle.high.toFixed(
          2
        )} <span>L</span>${candle.low.toFixed(
          2
        )} <span>C</span>${candle.close.toFixed(2)}</div>`,
      ];

      if (row?.ma200 !== null && row?.ma200 !== undefined) {
        lines.push(
          `<div class="tt-row tt-ma">${maLabel}: ${row.ma200.toFixed(
            2
          )}</div>`
        );
      }

      if (row?.resistance !== null && row?.resistance !== undefined) {
        lines.push(
          `<div class="tt-row tt-res">${resistanceLabel}: ${row.resistance.toFixed(
            2
          )}</div>`
        );
      }

      tooltipEl.innerHTML = lines.join("");

      const containerWidth = containerRef.current.clientWidth;
      const left =
        param.point.x > containerWidth - 190
          ? param.point.x - 200
          : param.point.x + 14;

      tooltipEl.style.left = `${left}px`;
      tooltipEl.style.top = `${Math.max(8, param.point.y - 10)}px`;
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
    };
  }, [data, resistanceLabel, maLabel]);

  return (
    <div className="tv-chart-wrapper">
      <div ref={containerRef} className="tv-chart" />
      <div ref={tooltipRef} className="tv-tooltip" style={{ display: "none" }} />
    </div>
  );
}

export default TradingChart;
