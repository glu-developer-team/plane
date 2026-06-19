/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import mermaid from "mermaid";
import { Minus } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { CloseIcon, PlusIcon } from "@plane/propel/icons";
import { cn } from "@plane/utils";

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 3;
const ZOOM_SPEED = 0.05;
const ZOOM_STEPS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const FULLSCREEN_THEME = "neutral";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  source: string;
};

function decodeHtmlEntities(text: string): string {
  if (!text.includes("&")) return text;
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}

function MermaidFullscreenModalContent({ isOpen, onClose, source }: Props) {
  const reactId = useId();
  const renderId = `mermaid-fullscreen-${reactId.replace(/:/g, "")}`;
  const modalRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef({ x: 0, y: 0 });
  const panOffset = useRef({ x: 0, y: 0 });

  const [svg, setSvg] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    panOffset.current = { x: 0, y: 0 };
  }, []);

  const handleClose = useCallback(() => {
    if (isDragging) return;
    onClose();
    resetView();
  }, [isDragging, onClose, resetView]);

  const handleMagnification = useCallback((direction: "increase" | "decrease") => {
    setZoom((prev) => {
      if (direction === "increase") {
        return ZOOM_STEPS.find((step) => step > prev) ?? MAX_ZOOM;
      }

      return [...ZOOM_STEPS].reverse().find((step) => step < prev) ?? MIN_ZOOM;
    });

    setPan({ x: 0, y: 0 });
    panOffset.current = { x: 0, y: 0 };
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "Escape" || e.key === "+" || e.key === "=" || e.key === "-") {
        e.preventDefault();
        e.stopPropagation();

        if (e.key === "Escape") handleClose();
        if (e.key === "+" || e.key === "=") handleMagnification("increase");
        if (e.key === "-") handleMagnification("decrease");
      }
    },
    [handleClose, handleMagnification, isOpen]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!contentRef.current || e.button !== 0 || isLoading || renderError) return;

    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    panOffset.current = { ...pan };
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;

      setPan({
        x: panOffset.current.x + (e.clientX - dragStart.current.x),
        y: panOffset.current.y + (e.clientY - dragStart.current.y),
      });
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (!isOpen || isLoading || renderError) return;

      e.preventDefault();

      const delta = e.deltaY;
      setZoom((prev) => {
        const direction = delta > 0 ? -1 : 1;
        const nextZoom = prev + direction * ZOOM_SPEED * Math.max(prev, 1);
        return Math.min(Math.max(nextZoom, MIN_ZOOM), MAX_ZOOM);
      });
    },
    [isLoading, isOpen, renderError]
  );

  useEffect(() => {
    if (!isOpen) return;

    resetView();

    const trimmed = decodeHtmlEntities(source).trim();
    if (!trimmed) {
      setSvg("");
      setRenderError("No diagram source to display.");
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setRenderError(null);
    setSvg("");

    const renderDiagram = async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: FULLSCREEN_THEME,
          securityLevel: "strict",
          fontFamily: "inherit",
        });

        const { svg: renderedSvg } = await mermaid.render(renderId, trimmed);
        if (!cancelled) {
          setSvg(renderedSvg);
          setRenderError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSvg("");
          setRenderError(err instanceof Error ? err.message : "Failed to render Mermaid diagram");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [isOpen, renderId, resetView, source]);

  useEffect(() => {
    if (!isOpen) return;

    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    window.addEventListener("wheel", handleWheel, { passive: false });

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("wheel", handleWheel);
    };
  }, [handleKeyDown, handleMouseMove, handleMouseUp, handleWheel, isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className={cn("mermaid-fullscreen-modal fixed inset-0 z-[9999] size-full bg-black/95", {
        "cursor-grabbing": isDragging,
        "cursor-grab": !isDragging && svg && !isLoading,
      })}
      role="dialog"
      aria-modal="true"
      aria-label="Fullscreen Mermaid diagram viewer"
    >
      <div
        ref={modalRef}
        role="presentation"
        onMouseDown={(e) => e.target === modalRef.current && handleClose()}
        className="relative grid size-full place-items-center overflow-hidden p-6"
      >
        <button
          type="button"
          onClick={handleClose}
          className="absolute top-6 right-6 z-10 grid size-8 place-items-center"
          aria-label="Close diagram viewer"
        >
          <CloseIcon className="size-8 text-white/60 transition-colors hover:text-white" />
        </button>

        <div
          ref={contentRef}
          role="img"
          aria-label="Mermaid diagram preview"
          className={cn(
            "mermaid-fullscreen-modal__diagram mermaid-diagram shadow-2xl max-h-[85vh] max-w-[95vw] overflow-auto rounded-xl bg-white p-8",
            {
              "pointer-events-none opacity-0": isLoading,
            }
          )}
          style={{
            transform: svg ? `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` : undefined,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.15s ease-out",
          }}
          onMouseDown={handleMouseDown}
        >
          {isLoading && <p className="text-sm text-neutral-500 min-w-80 text-center">Loading diagram...</p>}
          {!isLoading && renderError && <p className="text-sm text-red-600 min-w-80 text-center">{renderError}</p>}
          {!isLoading && !renderError && svg && <div dangerouslySetInnerHTML={{ __html: svg }} />}
        </div>

        <div className="fixed bottom-8 left-1/2 z-10 flex -translate-x-1/2 items-center justify-center gap-1 divide-x divide-subtle-1 rounded-md border border-subtle-1 bg-black py-2">
          <div className="flex items-center">
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleMagnification("decrease");
              }}
              className="grid size-6 place-items-center text-white/60 transition-colors duration-200 hover:text-white disabled:text-white/30"
              disabled={zoom <= MIN_ZOOM || isLoading || Boolean(renderError)}
              aria-label="Zoom out"
            >
              <Minus className="size-4" />
            </button>
            <span className="w-14 text-center text-13 text-white">{Math.round(100 * zoom)}%</span>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleMagnification("increase");
              }}
              className="grid size-6 place-items-center text-white/60 transition-colors duration-200 hover:text-white disabled:text-white/30"
              disabled={zoom >= MAX_ZOOM || isLoading || Boolean(renderError)}
              aria-label="Zoom in"
            >
              <PlusIcon className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function MermaidFullscreenModal(props: Props) {
  if (!props.isOpen) return null;

  const modal = <MermaidFullscreenModalContent {...props} />;

  if (typeof document !== "undefined" && document.body) {
    return ReactDOM.createPortal(modal, document.body);
  }

  return modal;
}
