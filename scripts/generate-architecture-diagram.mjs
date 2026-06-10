/**
 * Generate docs/diagrams/lms-architecture.tldr for tldraw.com / Cursor tldraw plugin.
 * Run: node scripts/generate-architecture-diagram.mjs
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>");
const raf = (cb) => setTimeout(cb, 0);
const caf = (id) => clearTimeout(id);
globalThis.document = dom.window.document;
globalThis.window = dom.window;
globalThis.requestAnimationFrame = raf;
globalThis.cancelAnimationFrame = caf;
dom.window.requestAnimationFrame = raf;
dom.window.cancelAnimationFrame = caf;

const {
  Editor,
  createShapeId,
  createTLStore,
  defaultAddFontsFromNode,
  defaultShapeUtils,
  serializeTldrawJson,
  tipTapDefaultExtensions,
  toRichText,
} = await import("tldraw");

const __dirname = dirname(fileURLToPath(import.meta.url));
const outPath = join(__dirname, "../docs/diagrams/lms-architecture.tldr");

const store = createTLStore({ shapeUtils: defaultShapeUtils });
const editor = new Editor({
  shapeUtils: defaultShapeUtils,
  bindingUtils: [],
  tools: [],
  store,
  getContainer: () => document.body,
  options: {
    text: {
      addFontsFromNode: defaultAddFontsFromNode,
      tipTapConfig: { extensions: tipTapDefaultExtensions },
    },
  },
});

const shapes = new Map();

function box(id, x, y, w, h, text, color = "blue") {
  const shapeId = createShapeId(id);
  editor.createShape({
    id: shapeId,
    type: "geo",
    x,
    y,
    props: {
      geo: "rectangle",
      w,
      h,
      color,
      fill: "semi",
      dash: "solid",
      size: "m",
      font: "draw",
      align: "middle",
      verticalAlign: "middle",
      richText: toRichText(text),
      labelColor: "black",
    },
  });
  shapes.set(id, shapeId);
}

function label(id, x, y, text, size = "l") {
  const shapeId = createShapeId(id);
  editor.createShape({
    id: shapeId,
    type: "text",
    x,
    y,
    props: {
      color: "black",
      size,
      font: "draw",
      textAlign: "start",
      autoSize: true,
      w: 400,
      richText: toRichText(text),
    },
  });
  shapes.set(id, shapeId);
}

function arrow(from, to, id) {
  const a = editor.getShape(shapes.get(from));
  const b = editor.getShape(shapes.get(to));
  if (!a || !b || a.type !== "geo" || b.type !== "geo") return;

  const ax = a.x + a.props.w / 2;
  const ay = a.y + a.props.h;
  const bx = b.x + b.props.w / 2;
  const by = b.y;

  editor.createShape({
    id: createShapeId(id),
    type: "arrow",
    x: ax,
    y: ay,
    props: {
      kind: "arc",
      color: "grey",
      labelColor: "black",
      fill: "none",
      dash: "draw",
      size: "m",
      arrowheadStart: "none",
      arrowheadEnd: "arrow",
      font: "draw",
      start: { x: 0, y: 0 },
      end: { x: bx - ax, y: by - ay },
      bend: 0,
      richText: toRichText(""),
    },
  });
}

// Title
label("title", 40, 20, "LMS MVP — Architecture & Design", "xl");
label(
  "subtitle",
  40,
  70,
  "Modular monolith · Reference · Catalog · Loan · ADR-001–020",
  "m"
);

// Presentation layer
label("lbl-pres", 40, 120, "Presentation", "l");
box("api", 40, 150, 220, 90, "FastAPI\n/api/v1/*\nJWT · RBAC · Idempotency", "violet");
box("ui", 280, 150, 180, 90, "Staff desk UI\n(phase 6)", "light-violet");

// Application layer
label("lbl-app", 40, 270, "Application", "l");
box("ref-api", 40, 300, 200, 80, "Reference\nService + Router", "blue");
box("cat-api", 260, 300, 200, 80, "Catalog\nService + Router", "green");
box("loan-api", 480, 300, 200, 80, "Loan\nService + Router", "orange");
box("orch", 260, 410, 280, 90, "CirculationOrchestrator\nCheckout · Return", "red");
box("queries", 560, 410, 200, 80, "Query handlers\nOpen · Overdue · Search", "yellow");

// Domain ports
label("lbl-ports", 40, 520, "Integration ports (ADR-004)", "l");
box("port-elig", 40, 550, 240, 70, "PatronEligibilityPort", "light-blue");
box("port-hold", 300, 550, 240, 70, "HoldingCirculationPort", "light-green");
box("port-policy", 560, 550, 240, 70, "PolicyResolverPort", "light-red");

// Domain aggregates
label("lbl-domain", 40, 640, "Domain aggregates", "l");
box(
  "ref-dom",
  40,
  670,
  200,
  100,
  "Reference\nPatron · PatronType\nClassSection · Block",
  "blue"
);
box(
  "cat-dom",
  260,
  670,
  200,
  100,
  "Catalog\nCatalog · Holding\nDRAFT→PUBLISHED",
  "green"
);
box(
  "loan-dom",
  480,
  670,
  200,
  100,
  "Loan\nLoan · LoanRuleSet\nOpen loan invariant",
  "orange"
);

// Infrastructure
label("lbl-infra", 40, 790, "Infrastructure", "l");
box(
  "db",
  40,
  820,
  260,
  90,
  "PostgreSQL 16\nAlembic · Row locks\nPartial unique index",
  "grey"
);
box("idemp", 320, 820, 220, 90, "Idempotency store\nCheckout / Return", "grey");
box("shared", 560, 820, 240, 90, "Shared\nAuth · Time TZ\nAsia/Kolkata", "grey");

// Cross-layer arrows
arrow("api", "ref-api", "a1");
arrow("api", "cat-api", "a2");
arrow("api", "loan-api", "a3");
arrow("api", "orch", "a4");
arrow("ui", "api", "a5");
arrow("orch", "port-elig", "a6");
arrow("orch", "port-hold", "a7");
arrow("orch", "port-policy", "a8");
arrow("port-elig", "ref-dom", "a9");
arrow("port-hold", "cat-dom", "a10");
arrow("port-policy", "loan-dom", "a11");
arrow("ref-api", "ref-dom", "a12");
arrow("cat-api", "cat-dom", "a13");
arrow("loan-api", "loan-dom", "a14");
arrow("ref-dom", "db", "a15");
arrow("cat-dom", "db", "a16");
arrow("loan-dom", "db", "a17");
arrow("orch", "idemp", "a18");
arrow("queries", "db", "a19");

// Design notes
box(
  "notes",
  720,
  150,
  340,
  320,
  "Key decisions\n• ADR-002: Orchestrator only cross-context writes\n• ADR-006: Single TX + FOR UPDATE on holding\n• ADR-017: Idempotency-Key header\n• D3: JWT ADMIN/LIBRARIAN/PATRON\n• D4: Librarian-only checkout\n• Import-linter: no cross-BC infra imports",
  "white"
);

const json = await serializeTldrawJson(editor);
editor.dispose();
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, json);
const recordCount = JSON.parse(json).records?.length ?? 0;
console.log(`Wrote ${outPath} (${recordCount} records)`);
process.exit(0);
