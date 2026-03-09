import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Receipt } from "@/types/receipt";
import { updateReceipt } from "@/services/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Save, Edit2, X, ChevronRight, ChevronDown } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface EditableReceiptTableProps {
  receipts: Receipt[];
  onReceiptUpdate?: (receiptId: string, updates: Partial<Receipt>) => void;
}

interface EditableField {
  [receiptId: string]: {
    merchant_name?: string;
    date?: string;
    total_amount?: number;
    vat_amount?: number;
    vat_percentage?: number;
    currency?: string;
  };
}

export function EditableReceiptTable({ receipts, onReceiptUpdate }: EditableReceiptTableProps) {
  const [editing, setEditing] = useState<{ [key: string]: string | null }>({});
  const [editedValues, setEditedValues] = useState<EditableField>({});
  const [saving, setSaving] = useState<{ [key: string]: boolean }>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatCurrency = (amount: number | null, currency: string | null) => {
    if (amount === null) return "";
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'EUR',
    }).format(amount);
  };

  const formatDate = (date: string | null) => {
    if (!date) return "";
    try {
      const d = new Date(date);
      return d.toISOString().split('T')[0];
    } catch {
      return date;
    }
  };

  const startEdit = (receiptId: string, field: string) => {
    setEditing({ ...editing, [`${receiptId}-${field}`]: field });
    const receipt = receipts.find(r => r.id === receiptId);
    if (receipt) {
      setEditedValues({
        ...editedValues,
        [receiptId]: {
          ...editedValues[receiptId],
          [field]: receipt[field as keyof Receipt] as any
        }
      });
    }
  };

  const cancelEdit = (receiptId: string, field: string) => {
    const key = `${receiptId}-${field}`;
    const newEditing = { ...editing };
    delete newEditing[key];
    setEditing(newEditing);
  };

  const updateFieldValue = (receiptId: string, field: string, value: any) => {
    setEditedValues({
      ...editedValues,
      [receiptId]: {
        ...editedValues[receiptId],
        [field]: value
      }
    });
  };

  const validateField = (field: string, value: any): boolean => {
    if (field === 'date') {
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (value && !dateRegex.test(value)) return false;
      if (value) {
        const d = new Date(value);
        return !isNaN(d.getTime());
      }
    }
    if (field === 'total_amount' || field === 'vat_amount' || field === 'vat_percentage') {
      if (value !== null && value !== undefined && value !== '') {
        const num = parseFloat(value);
        return !isNaN(num) && num >= 0;
      }
    }
    return true;
  };

  const saveField = async (receiptId: string, field: string) => {
    const receipt = receipts.find(r => r.id === receiptId);
    if (!receipt) return;

    const editedValue = editedValues[receiptId]?.[field as keyof EditableField[string]];
    const originalValue = receipt[field as keyof Receipt];

    if (editedValue === originalValue) {
      cancelEdit(receiptId, field);
      return;
    }

    if (!validateField(field, editedValue)) {
      toast({ title: "Validation error", description: `Invalid value for ${field}`, variant: "destructive" });
      return;
    }

    setSaving({ ...saving, [`${receiptId}-${field}`]: true });

    try {
      const updates: Partial<Receipt> = { [field]: editedValue };
      if (field === 'total_amount' || field === 'vat_amount' || field === 'vat_percentage') {
        if (editedValue !== null && editedValue !== undefined && editedValue !== '') {
          updates[field as keyof Receipt] = parseFloat(editedValue as string) as any;
        } else {
          updates[field as keyof Receipt] = null as any;
        }
      }

      await updateReceipt(parseInt(receiptId), updates);
      if (onReceiptUpdate) onReceiptUpdate(receiptId, updates);

      const receiptIndex = receipts.findIndex(r => r.id === receiptId);
      if (receiptIndex >= 0) {
        receipts[receiptIndex] = { ...receipts[receiptIndex], ...updates, modified: true };
      }

      cancelEdit(receiptId, field);
      toast({ title: "Updated", description: `${field} updated successfully` });
    } catch (error) {
      toast({ title: "Update failed", description: error instanceof Error ? error.message : "Failed to update receipt", variant: "destructive" });
    } finally {
      setSaving({ ...saving, [`${receiptId}-${field}`]: false });
    }
  };

  const hasUnsavedChanges = Object.keys(editedValues).length > 0 &&
    Object.values(editedValues).some(v => Object.keys(v).length > 0);

  const saveAllChanges = async () => {
    for (const [receiptId, changes] of Object.entries(editedValues)) {
      if (Object.keys(changes).length === 0) continue;
      const receipt = receipts.find(r => r.id === receiptId);
      if (!receipt) continue;

      setSaving({ ...saving, [receiptId]: true });
      try {
        const updates: Partial<Receipt> = {};
        for (const [field, value] of Object.entries(changes)) {
          if (field === 'total_amount' || field === 'vat_amount' || field === 'vat_percentage') {
            if (value !== null && value !== undefined && value !== '') {
              updates[field as keyof Receipt] = parseFloat(value as string) as any;
            } else {
              updates[field as keyof Receipt] = null as any;
            }
          } else {
            updates[field as keyof Receipt] = value as any;
          }
        }
        await updateReceipt(parseInt(receiptId), updates);
        if (onReceiptUpdate) onReceiptUpdate(receiptId, updates);
      } catch (error) {
        toast({ title: "Update failed", description: `Failed to update receipt ${receiptId}`, variant: "destructive" });
      } finally {
        setSaving({ ...saving, [receiptId]: false });
      }
    }
    setEditedValues({});
    toast({ title: "All changes saved", description: "All receipt updates have been saved" });
  };

  const renderEditableCell = (
    receiptId: string,
    field: string,
    value: any,
    type: 'text' | 'number' | 'date' = 'text'
  ) => {
    const editKey = `${receiptId}-${field}`;
    const isEditing = editing[editKey] === field;
    const isSaving = saving[editKey] || saving[receiptId];

    if (isEditing) {
      const editedValue = editedValues[receiptId]?.[field as keyof EditableField[string]] ?? value;
      return (
        <div className="flex items-center gap-2">
          <Input
            type={type}
            value={editedValue ?? ''}
            onChange={(e) => updateFieldValue(receiptId, field, e.target.value)}
            onBlur={() => {
              if (validateField(field, editedValue)) saveField(receiptId, field);
            }}
            className="h-8 w-full"
            disabled={isSaving}
          />
          <Button size="sm" variant="ghost" onClick={() => saveField(receiptId, field)} disabled={isSaving}>
            <Save className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="ghost" onClick={() => cancelEdit(receiptId, field)} disabled={isSaving}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2 group">
        <span>{value ?? "\u2014"}</span>
        <Button
          size="sm"
          variant="ghost"
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => startEdit(receiptId, field)}
        >
          <Edit2 className="h-3 w-3" />
        </Button>
      </div>
    );
  };

  /** Show per-rate breakdown in the VAT column when multiple rates exist */
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
    return renderEditableCell(receipt.id, 'vat_amount', receipt.vat_amount, 'number');
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
    return renderEditableCell(receipt.id, 'vat_percentage', receipt.vat_percentage, 'number');
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
      {hasUnsavedChanges && (
        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 flex items-center justify-between">
          <span className="text-sm text-yellow-800 dark:text-yellow-200">
            You have unsaved changes
          </span>
          <Button size="sm" onClick={saveAllChanges} variant="default">
            Save All Changes
          </Button>
        </div>
      )}
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
                  className={`border-b border-border hover:bg-muted/30 transition-colors ${
                    isExpanded ? "bg-muted/20" : ""
                  } ${receipt.modified ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}
                >
                  <TableCell
                    className="w-8 px-2 cursor-pointer"
                    onClick={() => hasItems(receipt) && toggleExpand(receipt.id)}
                  >
                    {hasItems(receipt) && (
                      <span className="text-muted-foreground">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-medium">
                    {renderEditableCell(receipt.id, 'merchant_name', receipt.store_name, 'text')}
                    {receipt.modified && (
                      <span className="ml-2 text-xs text-blue-600 dark:text-blue-400">modified</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {renderEditableCell(receipt.id, 'date', formatDate(receipt.date), 'date')}
                  </TableCell>
                  <TableCell className="font-medium">
                    {renderEditableCell(receipt.id, 'total_amount', receipt.total_amount, 'number')}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {renderVatSummary(receipt)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {renderVatPct(receipt)}
                  </TableCell>
                  <TableCell>
                    {renderEditableCell(receipt.id, 'currency', receipt.currency, 'text')}
                  </TableCell>
                  <TableCell>
                    {receipt.confidence_score !== null && receipt.confidence_score !== undefined ? (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
                        receipt.confidence_score >= 0.8
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : receipt.confidence_score >= 0.6
                          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                      }`}>
                        {Math.round(receipt.confidence_score * 100)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">{"\u2014"}</span>
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
