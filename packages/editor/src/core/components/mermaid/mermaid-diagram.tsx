/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import mermaid from "mermaid";
import { useEffect, useId, useState } from "react";

let mermaidInitialized = false;

function ensureMermaidInitialized() {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "default",
    securityLevel: "strict",
    fontFamily: "inherit",
  });
  mermaidInitialized = true;
}

type Props = {
  source: string;
};

function decodeHtmlEntities(text: string): string {
  if (!text.includes("&")) return text;
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}

export function MermaidDiagram({ source }: Props) {
  const reactId = useId();
  const renderId = `mermaid-${reactId.replace(/:/g, "")}`;
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmed = decodeHtmlEntities(source).trim();
    if (!trimmed) {
      setSvg("");
      setError(null);
      return;
    }

    let cancelled = false;

    const renderDiagram = async () => {
      try {
        ensureMermaidInitialized();
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
  }, [source, renderId]);

  if (!source.trim()) {
    return (
      <div className="mermaid-diagram mermaid-diagram--empty text-sm rounded-lg border border-subtle bg-layer-2 p-4 text-tertiary">
        Enter Mermaid diagram syntax below
      </div>
    );
  }

  if (error) {
    return (
      <div className="mermaid-diagram mermaid-diagram--error text-sm rounded-lg border border-danger-subtle bg-danger-subtle p-4 text-danger-primary">
        {error}
      </div>
    );
  }

  return (
    <div
      className="mermaid-diagram overflow-x-auto rounded-lg border border-subtle bg-layer-1 p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
