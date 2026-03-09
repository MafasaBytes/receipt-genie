import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Receipt } from "@/types/receipt";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronRight, ChevronDown } from "lucide-react";

interface ReceiptsTableProps {
  receipts: Receipt[];
}

export function ReceiptsTable({ receipts }: ReceiptsTableProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatCurrency = (amount: number | null, currency: string | null) => {
    if (amount === null) return "\u2014";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "EUR",
    }).format(amount);
  };

  const formatDate = (date: string | null) => {
    if (!date) return "\u2014";
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  /** Render the VAT column as a per-rate breakdown when available */
  const renderVatSummary = (receipt: Receipt) => {
    const bd = receipt.vat_breakdown;
    if (bd && bd.length > 1) {
      return (
        <div className="flex flex-col gap-0.5 text-xs">
          {bd.map((entry, i) => (
            <span key={i}>
              {entry.vat_rate}%: {formatCurrency(entry.tax_amount, receipt.currency)}
            </span>
          ))}
        </div>
      );
    }
    return formatCurrency(receipt.vat_amount, receipt.currency);
  };

  const renderVatPct = (receipt: Receipt) => {
    const bd = receipt.vat_breakdown;
    if (bd && bd.length > 1) {
      return (
        <span className="text-xs">
          {bd.map((e) => `${e.vat_rate}%`).join(" / ")}
        </span>
      );
    }
    return receipt.vat_percentage !== null ? `${receipt.vat_percentage}%` : "\u2014";
  };

  const hasItems = (receipt: Receipt) =>
    receipt.items && receipt.items.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full rounded-xl border border-border bg-card overflow-hidden shadow-card"
    >
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50">
            <TableHead className="w-8"></TableHead>
            <TableHead className="font-semibold">Store Name</TableHead>
            <TableHead className="font-semibold">Date</TableHead>
            <TableHead className="font-semibold">Total</TableHead>
            <TableHead className="font-semibold">VAT</TableHead>
            <TableHead className="font-semibold">VAT %</TableHead>
            <TableHead className="font-semibold">Currency</TableHead>
            <TableHead className="font-semibold">Accuracy</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {receipts.map((receipt, index) => {
            const isExpanded = expanded[receipt.id];
            const items = receipt.items || [];
            return (
              <>
                {/* Parent: receipt row */}
                <motion.tr
                  key={receipt.id}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={`border-b border-border hover:bg-muted/30 transition-colors cursor-pointer ${
                    isExpanded ? "bg-muted/20" : ""
                  }`}
                  onClick={() => hasItems(receipt) && toggleExpand(receipt.id)}
                >
                  <TableCell className="w-8 px-2">
                    {hasItems(receipt) && (
                      <span className="text-muted-foreground">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-medium">
                    {receipt.store_name || "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(receipt.date)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {formatCurrency(receipt.total_amount, receipt.currency)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {renderVatSummary(receipt)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {renderVatPct(receipt)}
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground">
                      {receipt.currency || "\u2014"}
                    </span>
                  </TableCell>
                  <TableCell>
                    {receipt.confidence_score !== null &&
                    receipt.confidence_score !== undefined ? (
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
                          receipt.confidence_score >= 0.8
                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                            : receipt.confidence_score >= 0.6
                            ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                            : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                        }`}
                      >
                        {Math.round(receipt.confidence_score * 100)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">
                        {"\u2014"}
                      </span>
                    )}
                  </TableCell>
                </motion.tr>

                {/* Children: item rows */}
                <AnimatePresence>
                  {isExpanded &&
                    items.map((item, itemIdx) => (
                      <motion.tr
                        key={`${receipt.id}-item-${itemIdx}`}
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.15 }}
                        className="bg-muted/10 border-b border-border/50 text-sm"
                      >
                        <TableCell className="w-8 px-2"></TableCell>
                        <TableCell className="pl-8 text-muted-foreground" colSpan={2}>
                          <span className="text-xs text-muted-foreground/60 mr-2">
                            {item.quantity != null && item.quantity !== 1
                              ? `${item.quantity}x`
                              : "\u00B7"}
                          </span>
                          {item.name || "Unknown item"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatCurrency(item.line_total, receipt.currency)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {item.vat_amount != null
                            ? formatCurrency(item.vat_amount, receipt.currency)
                            : "\u2014"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {item.vat_rate != null ? `${item.vat_rate}%` : "\u2014"}
                        </TableCell>
                        <TableCell colSpan={2}></TableCell>
                      </motion.tr>
                    ))}
                </AnimatePresence>
              </>
            );
          })}
        </TableBody>
      </Table>
    </motion.div>
  );
}
