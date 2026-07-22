/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// helpers
import { slugifyHeading } from "@/helpers/slugify-heading";
// types
import type { IMarking } from "@/types";

export type HeadingExtensionStorage = {
  headings: IMarking[];
};

type HeadingListPluginState = {
  headings: IMarking[];
  decorations: DecorationSet;
};

declare module "@tiptap/core" {
  interface Storage {
    [CORE_EXTENSIONS.HEADINGS_LIST]: HeadingExtensionStorage;
  }
}

function buildHeadingListState(doc: ProseMirrorNode): HeadingListPluginState {
  const headings: IMarking[] = [];
  const decorationList: Decoration[] = [];
  const slugCounts = new Map<string, number>();
  let h1Sequence = 0;
  let h2Sequence = 0;
  let h3Sequence = 0;

  doc.descendants((node, pos) => {
    if (node.type.name !== "heading") return;

    const level = node.attrs.level as number;
    const text = node.textContent;
    const baseSlug = slugifyHeading(text);
    const nextCount = (slugCounts.get(baseSlug) ?? 0) + 1;
    slugCounts.set(baseSlug, nextCount);
    const slug = nextCount === 1 ? baseSlug : `${baseSlug}-${nextCount}`;
    const sequence = level === 1 ? ++h1Sequence : level === 2 ? ++h2Sequence : ++h3Sequence;

    headings.push({
      type: "heading",
      level,
      text,
      sequence,
      slug,
    });

    decorationList.push(
      Decoration.node(pos, pos + node.nodeSize, {
        id: slug,
      })
    );
  });

  return {
    headings,
    decorations: DecorationSet.create(doc, decorationList),
  };
}

export const HeadingListExtension = Extension.create<unknown, HeadingExtensionStorage>({
  name: CORE_EXTENSIONS.HEADINGS_LIST,

  addStorage() {
    return {
      headings: [] as IMarking[],
    };
  },

  addProseMirrorPlugins() {
    const headingStorage = this.storage;

    return [
      new Plugin<HeadingListPluginState>({
        key: new PluginKey("heading-list"),
        state: {
          init: (_, state) => {
            const next = buildHeadingListState(state.doc);
            headingStorage.headings = next.headings;
            return next;
          },
          apply: (tr, value, _oldState, newState) => {
            if (!tr.docChanged) return value;
            const next = buildHeadingListState(newState.doc);
            headingStorage.headings = next.headings;
            return next;
          },
        },
        props: {
          decorations(state) {
            return this.getState(state)?.decorations ?? DecorationSet.empty;
          },
        },
      }),
    ];
  },

  getHeadings() {
    return this.storage.headings;
  },
});
