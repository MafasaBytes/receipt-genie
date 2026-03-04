import { ReceiptScanner } from "@/components/receipt-scanner/ReceiptScanner";

const Index = () => {
  return (
    <main className="min-h-screen bg-background">
      <div className="container py-12 md:py-20 px-4">
        <ReceiptScanner />
      </div>
      
      {/* Footer */}
      <footer className="border-t border-border py-6">
        <div className="container px-4">
          <p className="text-center text-sm text-muted-foreground">
            Receipt Scanner • Local Processing • Your data stays private
          </p>
        </div>
      </footer>
    </main>
  );
};

export default Index;
