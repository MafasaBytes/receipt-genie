import { motion } from "framer-motion";
import { Receipt } from "@/types/receipt";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface ReceiptsTableProps {
  receipts: Receipt[];
}

export function ReceiptsTable({ receipts }: ReceiptsTableProps) {
  const formatCurrency = (amount: number | null, currency: string | null) => {
    if (amount === null) return "—";
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'EUR',
    }).format(amount);
  };

  const formatDate = (date: string | null) => {
    if (!date) return "—";
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

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
            <TableHead className="font-semibold">Store Name</TableHead>
            <TableHead className="font-semibold">Date</TableHead>
            <TableHead className="font-semibold text-right">Total</TableHead>
            <TableHead className="font-semibold text-right">VAT</TableHead>
            <TableHead className="font-semibold text-right">VAT %</TableHead>
            <TableHead className="font-semibold text-center">Currency</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {receipts.map((receipt, index) => (
            <motion.tr
              key={receipt.id}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
            >
              <TableCell className="font-medium">
                {receipt.store_name || "—"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(receipt.date)}
              </TableCell>
              <TableCell className="text-right font-medium">
                {formatCurrency(receipt.total_amount, receipt.currency)}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatCurrency(receipt.vat_amount, receipt.currency)}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {receipt.vat_percentage !== null ? `${receipt.vat_percentage}%` : "—"}
              </TableCell>
              <TableCell className="text-center">
                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground">
                  {receipt.currency || "—"}
                </span>
              </TableCell>
            </motion.tr>
          ))}
        </TableBody>
      </Table>
    </motion.div>
  );
}
