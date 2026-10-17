// Illustrative UI fixture shown when no analysis is loaded. Same shape as GET /api/analyses/{id}/distribution.
import type { Graph } from "@/lib/api";

export const demoGraph: Graph = {
  nodes: [
    { id: "root", label: "FOOD PROCESSING", detail: "Main distributor", kind: "root" },
    { id: "protein", label: "Protein cold-chain", kind: "route" },
    { id: "marinades", label: "Broth & marinades", kind: "route" },
    { id: "produce", label: "Pre-cut produce", kind: "route" },
    { id: "dry", label: "Dry goods", kind: "route" },
    { id: "rm402", label: "RM-402 · Marinated chicken", kind: "batch", flagged: true },
    { id: "sauce", label: "Central kitchen supply", kind: "batch" },
    { id: "grill", label: "Restaurant supply", kind: "batch" },
    { id: "canteen", label: "Industrial canteen", kind: "batch" },
    { id: "cloud", label: "Cloud kitchen", kind: "batch" },
    { id: "bakery", label: "Bakery supply", kind: "batch" },
    { id: "hotel", label: "Hospitality kitchen", kind: "batch" },
    { id: "shipment:SHIP-017", label: "Central Kitchen, QSR Group A", detail: "SHIP-017", kind: "recipient", flagged: true },
    { id: "shipment:SHIP-018", label: "Ramen Production Kitchen", detail: "SHIP-018", kind: "recipient" },
    { id: "central", label: "Central Kitchen B", kind: "recipient" },
    { id: "restaurant", label: "Restaurant & Grill", kind: "recipient" },
    { id: "canteen-dest", label: "Industrial Canteen", kind: "recipient" },
    { id: "cloud-dest", label: "Cloud Kitchen North", kind: "recipient" },
    { id: "bakery-dest", label: "Bakery Production B2B", kind: "recipient" },
    { id: "hotel-dest", label: "Banquet & Hotel Kitchen", kind: "recipient" },
  ],
  edges: [
    ["root", "protein"], ["root", "marinades"], ["root", "produce"], ["root", "dry"],
    ["protein", "rm402"], ["rm402", "shipment:SHIP-017"], ["rm402", "shipment:SHIP-018"],
    ["marinades", "sauce"], ["marinades", "grill"], ["sauce", "central"], ["grill", "restaurant"],
    ["produce", "canteen"], ["produce", "cloud"], ["canteen", "canteen-dest"], ["cloud", "cloud-dest"],
    ["dry", "bakery"], ["dry", "hotel"], ["bakery", "bakery-dest"], ["hotel", "hotel-dest"],
  ],
};
