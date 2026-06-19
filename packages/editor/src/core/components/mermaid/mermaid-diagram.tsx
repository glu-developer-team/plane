/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import mermaid from "mermaid";
import { useEffect, useId, useState } from "react";
import { FullScreenPanelIcon } from "@plane/propel/icons";
import { cn } from "@plane/utils";
import { normalizeMermaidSource } from "@/extensions/code/utils/normalize-mermaid-source";
import { MermaidFullscreenModal } from "./mermaid-fullscreen-modal";
import type { TMermaidTheme } from "./use-editor-theme";
import { useEditorTheme } from "./use-editor-theme";

function configureMermaid(theme: TMermaidTheme) {
  mermaid.initialize({
    startOnLoad: false,
    theme,
    securityLevel: "strict",
    fontFamily: "inherit",
  });
}

type Props = {
  source: string;
};

export function MermaidDiagram({ source }: Props) {
  const reactId = useId();
  const renderId = `mermaid-${reactId.replace(/:/g, "")}`;
  const editorTheme = useEditorTheme();
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isFullscreenOpen, setIsFullscreenOpen] = useState(false);

  useEffect(() => {
    const trimmed = normalizeMermaidSource(source);
    if (!trimmed) {
      setSvg("");
      setError(null);
      return;
    }

    let cancelled = false;

    const renderDiagram = async () => {
      try {
        configureMermaid(editorTheme);
        const { svg: renderedSvg } = await mermaid.render(renderId, trimmed);
        if (!cancelled) {
          setSvg(renderedSvg);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSvg("");
          setError(err instanceof Error ? err.message : "Failed to render Mermaid diagram");
        }
      }
    };

    void renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [source, renderId, editorTheme]);

  const openFullscreen = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsFullscreenOpen(true);
  };

  if (!source.trim()) {
    return (
      <div
        contentEditable={false}
        className="mermaid-diagram mermaid-diagram--empty text-sm rounded-lg border border-subtle bg-layer-2 p-4 text-tertiary"
      >
        Enter Mermaid diagram syntax below
      </div>
    );
  }

  if (error) {
    return (
      <div
        contentEditable={false}
        className="mermaid-diagram mermaid-diagram--error text-sm rounded-lg border border-danger-subtle bg-danger-subtle p-4 text-danger-primary"
      >
        {error}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        contentEditable={false}
        className="mermaid-diagram group/mermaid-diagram relative block w-full cursor-zoom-in overflow-x-auto rounded-lg border border-subtle bg-layer-1 p-4 text-left"
        data-mermaid-theme={editorTheme}
        onClick={openFullscreen}
        aria-label="Open diagram in fullscreen"
      >
        <span
          className={cn(
            "absolute top-2 left-2 z-10 grid size-8 place-items-center rounded-md border border-subtle bg-layer-1 text-tertiary opacity-0 backdrop-blur-sm transition duration-150 ease-in-out",
            "group-hover/mermaid-diagram:opacity-100"
          )}
          aria-hidden
        >
          <FullScreenPanelIcon className="size-4" />
        </span>

        <div dangerouslySetInnerHTML={{ __html: svg }} />
      </button>

      <MermaidFullscreenModal isOpen={isFullscreenOpen} source={source} onClose={() => setIsFullscreenOpen(false)} />
    </>
  );
}
