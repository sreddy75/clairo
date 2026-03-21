/**
 * Category taxonomy for client transaction classification.
 *
 * Clients classify transactions using plain-English categories.
 * The AI then maps these to BAS tax codes. Clients never see tax codes.
 *
 * Must stay in sync with backend/app/modules/bas/classification_constants.py
 */

export interface ClassificationCategory {
  id: string;
  label: string;
  group: "expense" | "income" | "special";
  receiptAlways: boolean;
}

export const EXPENSE_CATEGORIES: ClassificationCategory[] = [
  { id: "office_supplies", label: "Office supplies & stationery", group: "expense", receiptAlways: false },
  { id: "computer_it", label: "Computer & IT equipment", group: "expense", receiptAlways: true },
  { id: "tools_equipment", label: "Tools & equipment", group: "expense", receiptAlways: true },
  { id: "travel_transport", label: "Travel & transport", group: "expense", receiptAlways: false },
  { id: "fuel_vehicle", label: "Fuel & vehicle expenses", group: "expense", receiptAlways: false },
  { id: "meals_entertainment", label: "Meals & entertainment", group: "expense", receiptAlways: true },
  { id: "advertising_marketing", label: "Advertising & marketing", group: "expense", receiptAlways: false },
  { id: "professional_services", label: "Professional services (legal, accounting)", group: "expense", receiptAlways: false },
  { id: "insurance", label: "Insurance", group: "expense", receiptAlways: false },
  { id: "rent_property", label: "Rent & property", group: "expense", receiptAlways: false },
  { id: "phone_internet", label: "Phone & internet", group: "expense", receiptAlways: false },
  { id: "subscriptions_software", label: "Subscriptions & software", group: "expense", receiptAlways: false },
  { id: "stock_inventory", label: "Stock & inventory", group: "expense", receiptAlways: false },
  { id: "subcontractor", label: "Subcontractor payment", group: "expense", receiptAlways: true },
  { id: "bank_fees", label: "Bank fees & charges", group: "expense", receiptAlways: false },
  { id: "government_fees", label: "Government fees & charges", group: "expense", receiptAlways: false },
  { id: "training_education", label: "Training & education", group: "expense", receiptAlways: false },
  { id: "donations_gifts", label: "Donations & gifts", group: "expense", receiptAlways: false },
];

export const INCOME_CATEGORIES: ClassificationCategory[] = [
  { id: "sale_of_goods", label: "Sale of goods", group: "income", receiptAlways: false },
  { id: "service_income", label: "Service income", group: "income", receiptAlways: false },
  { id: "rental_income", label: "Rental income", group: "income", receiptAlways: false },
  { id: "interest_received", label: "Interest received", group: "income", receiptAlways: false },
  { id: "government_grant", label: "Government grant", group: "income", receiptAlways: false },
];

export const SPECIAL_CATEGORIES: ClassificationCategory[] = [
  { id: "personal", label: "Personal expense — not business", group: "special", receiptAlways: false },
  { id: "dont_know", label: "I don't know — my accountant can decide", group: "special", receiptAlways: false },
  { id: "other", label: "Other (please describe)", group: "special", receiptAlways: false },
];

export const ALL_CATEGORIES: ClassificationCategory[] = [
  ...EXPENSE_CATEGORIES,
  ...INCOME_CATEGORIES,
  ...SPECIAL_CATEGORIES,
];

const CATEGORY_MAP = new Map(ALL_CATEGORIES.map((c) => [c.id, c]));

export function getCategoryById(id: string): ClassificationCategory | undefined {
  return CATEGORY_MAP.get(id);
}

export function getCategoryLabel(id: string): string {
  return CATEGORY_MAP.get(id)?.label ?? id;
}
