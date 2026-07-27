import { AnimatePresence, motion } from "framer-motion";
import {
  Download,
  Eraser,
  Expand,
  Hand,
  Minus,
  Pencil,
  Plus,
  RotateCcw,
  Undo2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  PointerEvent as ReactPointerEvent,
  WheelEvent as ReactWheelEvent,
} from "react";

import { fetchAuthenticatedFile } from "../../lib/api";
import { useI18n } from "../../lib/i18n";

type Point = { x: number; y: number };
type Stroke = { points: Point[]; color: string; width: number };
type Tool = "pan" | "draw";

interface ImageReviewModalProps {
  open: boolean;
  onClose: () => void;
  imageUrl: string;
  title: string;
  subtitle?: string;
  annotationKey?: string;
}

const COLORS = ["#2dd4bf", "#8b8cf8", "#fb7185", "#f4b84a", "#ffffff"];

export function ImageReviewModal({
  open,
  onClose,
  imageUrl,
  title,
  subtitle,
  annotationKey,
}: ImageReviewModalProps) {
  const { t } = useI18n();
  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const panPointerRef = useRef<number | null>(null);
  const panOriginRef = useRef<Point | null>(null);
  const drawPointerRef = useRef<number | null>(null);
  const loadTimeoutRef = useRef<number | null>(null);

  const [tool, setTool] = useState<Tool>("pan");
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [draftStroke, setDraftStroke] = useState<Stroke | null>(null);
  const [color, setColor] = useState(COLORS[0]);
  const [lineWidth, setLineWidth] = useState(7);

  const storageKey = useMemo(
    () => (annotationKey ? `eyeai-annotation:${annotationKey}` : null),
    [annotationKey],
  );

  useEffect(() => {
    if (!open || !storageKey) return;
    try {
      const stored = localStorage.getItem(storageKey);
      setStrokes(stored ? (JSON.parse(stored) as Stroke[]) : []);
    } catch {
      setStrokes([]);
    }
  }, [open, storageKey]);

  useEffect(() => {
    if (!open || !storageKey) return;
    localStorage.setItem(storageKey, JSON.stringify(strokes));
  }, [open, storageKey, strokes]);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    let nextObjectUrl: string | null = null;

    setLoaded(false);
    setLoadError(null);
    setObjectUrl(null);
    setNaturalSize({ width: 0, height: 0 });
    setScale(1);
    setOffset({ x: 0, y: 0 });

    loadTimeoutRef.current = window.setTimeout(() => {
      if (!cancelled) setLoadError(t("imageLoadFailed"));
    }, 30000);

    const load = async () => {
      try {
        if (/^(blob:|data:)/i.test(imageUrl)) {
          if (!cancelled) setObjectUrl(imageUrl);
          return;
        }

        const blob = await fetchAuthenticatedFile(imageUrl);
        if (cancelled) return;

        nextObjectUrl = URL.createObjectURL(blob);
        setObjectUrl(nextObjectUrl);
      } catch (error) {
        if (!cancelled) {
          if (loadTimeoutRef.current) window.clearTimeout(loadTimeoutRef.current);
          setLoadError(error instanceof Error ? error.message : t("imageLoadFailed"));
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      if (loadTimeoutRef.current) window.clearTimeout(loadTimeoutRef.current);
      if (nextObjectUrl) URL.revokeObjectURL(nextObjectUrl);
    };
  }, [imageUrl, open, reloadKey, t]);

  const resetView = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport || !naturalSize.width || !naturalSize.height) return;

    const fitScale = Math.min(
      (viewport.clientWidth - 48) / naturalSize.width,
      (viewport.clientHeight - 48) / naturalSize.height,
      1,
    );

    setScale(Math.max(fitScale, 0.08));
    setOffset({ x: 0, y: 0 });
  }, [naturalSize]);

  useEffect(() => {
    if (!loaded) return;
    requestAnimationFrame(resetView);
  }, [loaded, resetView]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        setStrokes((items) => items.slice(0, -1));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  const stagePoint = (event: ReactPointerEvent<SVGSVGElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * naturalSize.width,
      y: ((event.clientY - rect.top) / rect.height) * naturalSize.height,
    };
  };

  const beginDraw = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (tool !== "draw" || !loaded) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    drawPointerRef.current = event.pointerId;
    setDraftStroke({ points: [stagePoint(event)], color, width: lineWidth });
  };

  const continueDraw = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (drawPointerRef.current !== event.pointerId || !draftStroke) return;
    const point = stagePoint(event);
    setDraftStroke((current) =>
      current ? { ...current, points: [...current.points, point] } : current,
    );
  };

  const finishDraw = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (drawPointerRef.current !== event.pointerId) return;
    if (draftStroke && draftStroke.points.length > 1) {
      setStrokes((items) => [...items, draftStroke]);
    }
    setDraftStroke(null);
    drawPointerRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (tool !== "pan" || !loaded) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    panPointerRef.current = event.pointerId;
    panOriginRef.current = {
      x: event.clientX - offset.x,
      y: event.clientY - offset.y,
    };
  };

  const continuePan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (panPointerRef.current !== event.pointerId || !panOriginRef.current) return;
    setOffset({
      x: event.clientX - panOriginRef.current.x,
      y: event.clientY - panOriginRef.current.y,
    });
  };

  const finishPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (panPointerRef.current !== event.pointerId) return;
    panPointerRef.current = null;
    panOriginRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const onWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    if (!loaded) return;
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    setScale((value) => Math.min(8, Math.max(0.08, value * factor)));
  };

  const downloadAnnotated = () => {
    const image = imageRef.current;
    if (!image || !naturalSize.width || !naturalSize.height) return;

    const canvas = document.createElement("canvas");
    canvas.width = naturalSize.width;
    canvas.height = naturalSize.height;
    const context = canvas.getContext("2d");
    if (!context) return;

    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    for (const stroke of strokes) {
      if (stroke.points.length < 2) continue;
      context.strokeStyle = stroke.color;
      context.lineWidth = stroke.width;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.beginPath();
      stroke.points.forEach((point, index) => {
        if (index === 0) context.moveTo(point.x, point.y);
        else context.lineTo(point.x, point.y);
      });
      context.stroke();
    }

    const anchor = document.createElement("a");
    anchor.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "eyeai-image"}-review.png`;
    anchor.href = canvas.toDataURL("image/png");
    anchor.click();
  };

  const enterFullscreen = async () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (document.fullscreenElement) await document.exitFullscreen();
    else await viewport.requestFullscreen();
  };

  const visibleStrokes = draftStroke ? [...strokes, draftStroke] : strokes;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[160] flex flex-col bg-[#020711]/95 backdrop-blur-xl"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#07111f]/94 px-4 py-3 text-white sm:px-6">
            <div className="min-w-0">
              <div className="truncate text-sm font-extrabold sm:text-base">{title}</div>
              {subtitle ? <div className="mt-0.5 truncate text-xs text-slate-400">{subtitle}</div> : null}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <ToolbarButton active={tool === "pan"} label={t("panTool")} onClick={() => setTool("pan")} icon={<Hand size={17} />} />
              <ToolbarButton active={tool === "draw"} label={t("drawTool")} onClick={() => setTool("draw")} icon={<Pencil size={17} />} />
              <span className="mx-1 h-6 w-px bg-white/12" />
              <ToolbarButton label={t("zoomOut")} onClick={() => setScale((value) => Math.max(0.08, value / 1.2))} icon={<Minus size={17} />} />
              <ToolbarButton label={t("zoomIn")} onClick={() => setScale((value) => Math.min(8, value * 1.2))} icon={<Plus size={17} />} />
              <ToolbarButton label={t("resetView")} onClick={resetView} icon={<RotateCcw size={17} />} />
              <ToolbarButton label={t("fullscreen")} onClick={enterFullscreen} icon={<Expand size={17} />} />
              <span className="mx-1 h-6 w-px bg-white/12" />
              <ToolbarButton label={t("undo")} disabled={!strokes.length} onClick={() => setStrokes((items) => items.slice(0, -1))} icon={<Undo2 size={17} />} />
              <ToolbarButton label={t("clearAnnotations")} disabled={!strokes.length} onClick={() => setStrokes([])} icon={<Eraser size={17} />} />
              <ToolbarButton label={t("downloadAnnotated")} disabled={!loaded} onClick={downloadAnnotated} icon={<Download size={17} />} />
              <ToolbarButton label={t("close")} onClick={onClose} icon={<X size={19} />} />
            </div>
          </div>

          {tool === "draw" ? (
            <div className="flex flex-wrap items-center justify-center gap-3 border-b border-white/10 bg-[#07111f]/86 px-4 py-2 text-white">
              <span className="text-xs font-bold text-slate-400">{t("annotationColor")}</span>
              <div className="flex items-center gap-1.5">
                {COLORS.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setColor(item)}
                    className={`h-6 w-6 rounded-full border-2 transition-transform ${color === item ? "scale-110 border-white" : "border-white/25"}`}
                    style={{ backgroundColor: item }}
                    aria-label={item}
                  />
                ))}
              </div>
              <span className="text-xs font-bold text-slate-400">{t("brushSize")}</span>
              <input
                type="range"
                min="2"
                max="26"
                value={lineWidth}
                onChange={(event) => setLineWidth(Number(event.target.value))}
                className="w-28 accent-teal-400"
              />
              <span className="w-6 text-xs tabular-nums text-slate-300">{lineWidth}</span>
            </div>
          ) : null}

          <div
            ref={viewportRef}
            className={`relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_center,#132238_0%,#07111f_56%,#020711_100%)] ${tool === "pan" ? "cursor-grab active:cursor-grabbing" : "cursor-crosshair"}`}
            style={{ touchAction: "none" }}
            onPointerDown={beginPan}
            onPointerMove={continuePan}
            onPointerUp={finishPan}
            onPointerCancel={finishPan}
            onWheel={onWheel}
          >
            {!objectUrl && !loadError ? (
              <div className="flex flex-col items-center gap-3 text-slate-300">
                <span className="h-9 w-9 animate-spin rounded-full border-2 border-teal-300/30 border-t-teal-300" />
                <span className="text-sm font-semibold">{t("loadingImage")}</span>
              </div>
            ) : null}

            {loadError ? (
              <div className="mx-5 max-w-lg rounded-2xl border border-rose-300/15 bg-rose-500/10 p-5 text-center text-rose-200">
                <div className="text-sm font-bold">{t("imageLoadFailed")}</div>
                <div className="mt-2 break-all text-xs text-rose-200/75">{loadError}</div>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="rounded-xl bg-white/10 px-4 py-2 text-xs font-bold text-white hover:bg-white/15">
                    {t("retry")}
                  </button>
                  <button type="button" onClick={() => window.open(imageUrl, "_blank", "noopener,noreferrer")} className="rounded-xl border border-white/15 px-4 py-2 text-xs font-bold text-white hover:bg-white/[0.08]">
                    {t("openImage")}
                  </button>
                </div>
              </div>
            ) : null}

            {objectUrl ? (
              <div
                className={`relative shrink-0 select-none ${loaded ? "block" : "invisible"}`}
                style={{
                  width: naturalSize.width || 1,
                  height: naturalSize.height || 1,
                  transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${scale})`,
                  transformOrigin: "center center",
                }}
              >
                <img
                  ref={imageRef}
                  src={objectUrl}
                  alt={title}
                  draggable={false}
                  className="absolute inset-0 h-full w-full rounded-xl object-contain shadow-2xl"
                  onLoad={(event) => {
                    const image = event.currentTarget;
                    setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
                    if (loadTimeoutRef.current) window.clearTimeout(loadTimeoutRef.current);
                    setLoaded(true);
                    setLoadError(null);
                  }}
                  onError={() => {
                    if (loadTimeoutRef.current) window.clearTimeout(loadTimeoutRef.current);
                    setLoadError(t("imageLoadFailed"));
                  }}
                />

                {loaded ? (
                  <svg
                    className={`absolute inset-0 h-full w-full rounded-xl ${tool === "draw" ? "pointer-events-auto" : "pointer-events-none"}`}
                    viewBox={`0 0 ${naturalSize.width} ${naturalSize.height}`}
                    preserveAspectRatio="none"
                    onPointerDown={beginDraw}
                    onPointerMove={continueDraw}
                    onPointerUp={finishDraw}
                    onPointerCancel={finishDraw}
                  >
                    {visibleStrokes.map((stroke, index) => (
                      <polyline
                        key={`${index}-${stroke.points.length}`}
                        points={stroke.points.map((point) => `${point.x},${point.y}`).join(" ")}
                        fill="none"
                        stroke={stroke.color}
                        strokeWidth={stroke.width}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        vectorEffect="non-scaling-stroke"
                      />
                    ))}
                  </svg>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 bg-[#07111f]/94 px-4 py-2.5 text-xs text-slate-400 sm:px-6">
            <span>{t("annotationDisclaimer")}</span>
            <span className="font-mono tabular-nums">{Math.round(scale * 100)}%</span>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function ToolbarButton({
  icon,
  label,
  active = false,
  disabled = false,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`flex h-9 w-9 items-center justify-center rounded-xl border text-slate-200 transition-all disabled:cursor-not-allowed disabled:opacity-30 ${
        active
          ? "border-teal-300/45 bg-teal-300/16 text-teal-200"
          : "border-white/10 bg-white/5 hover:bg-white/10"
      }`}
    >
      {icon}
    </button>
  );
}
