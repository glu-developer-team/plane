/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { NodeViewContent, NodeViewWrapper, useCurrentEditor } from "@tiptap/react";
import { CheckIcon } from "lucide-react";
import { useState } from "react";
import { CopyIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import { cn } from "@plane/utils";
import { MermaidDiagram } from "@/core/components/mermaid/mermaid-diagram";
import type { TCodeBlockAttributes } from "./types";
import { ECodeBlockAttributeNames } from "./types";

type Props = {
  node: ProseMirrorNode;
};

export function CodeBlockComponent({ node }: Props) {
  const { editor } = useCurrentEditor();
  const [copied, setCopied] = useState(false);
  const attrs = node.attrs as TCodeBlockAttributes;
  const language = attrs[ECodeBlockAttributeNames.LANGUAGE];
  const isMermaid = language === "mermaid";
  const isEditable = editor?.isEditable ?? false;

  const copyToClipboard = async (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    try {
      await navigator.clipboard.writeText(node.textContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1000);
    } catch {
      setCopied(false);
    }
    e.preventDefault();
    e.stopPropagation();
  };

  if (isMermaid) {
    return (
      <NodeViewWrapper
        key={attrs[ECodeBlockAttributeNames.ID]}
        className="code-block mermaid-block group/code relative"
      >
        <Tooltip tooltipContent="Copy diagram source">
          <button
            type="button"
            className={cn(
              "group/button absolute top-2 right-2 z-10 hidden size-8 items-center justify-center rounded-md border border-subtle bg-layer-1 backdrop-blur-sm transition duration-150 ease-in-out group-hover/code:flex",
              {
                "bg-success-subtle hover:bg-success-subtle-1 active:bg-success-subtle-1": copied,
              }
            )}
            onClick={(e) => void copyToClipboard(e)}
          >
            {copied ? (
              <CheckIcon className="h-3 w-3 text-success-primary" strokeWidth={3} />
            ) : (
              <CopyIcon className="h-3 w-3 text-tertiary group-hover/button:text-primary" />
            )}
          </button>
        </Tooltip>

        <MermaidDiagram source={node.textContent} />

        {isEditable ? (
          <pre className="mt-2 rounded-lg bg-layer-3 p-4 text-primary">
            <NodeViewContent as="code" className="whitespace-pre-wrap" />
          </pre>
        ) : (
          <NodeViewContent as="code" className="hidden" />
        )}
      </NodeViewWrapper>
    );
  }

  return (
    <NodeViewWrapper key={attrs[ECodeBlockAttributeNames.ID]} className="code-block group/code relative">
      <Tooltip tooltipContent="Copy code">
        <button
          type="button"
          className={cn(
            "group/button absolute top-2 right-2 z-10 hidden size-8 items-center justify-center rounded-md border border-subtle bg-layer-1 backdrop-blur-sm transition duration-150 ease-in-out group-hover/code:flex",
            {
              "bg-success-subtle hover:bg-success-subtle-1 active:bg-success-subtle-1": copied,
            }
          )}
          onClick={(e) => void copyToClipboard(e)}
        >
          {copied ? (
            <CheckIcon className="h-3 w-3 text-success-primary" strokeWidth={3} />
          ) : (
            <CopyIcon className="h-3 w-3 text-tertiary group-hover/button:text-primary" />
          )}
        </button>
      </Tooltip>

      <pre className="my-2 rounded-lg bg-layer-3 p-4 text-primary">
        <NodeViewContent as="code" className="whitespace-pre-wrap" />
      </pre>
    </NodeViewWrapper>
  );
}
