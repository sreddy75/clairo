'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import type { FinancialsInput } from '@/types/tax-planning';

const formSchema = z.object({
  revenue: z.coerce.number().min(0, 'Must be 0 or more'),
  other_income: z.coerce.number().min(0, 'Must be 0 or more'),
  cost_of_sales: z.coerce.number().min(0, 'Must be 0 or more'),
  operating_expenses: z.coerce.number().min(0, 'Must be 0 or more'),
  payg_instalments: z.coerce.number().min(0, 'Must be 0 or more'),
  payg_withholding: z.coerce.number().min(0, 'Must be 0 or more'),
  franking_credits: z.coerce.number().min(0, 'Must be 0 or more'),
  turnover: z.coerce.number().min(0, 'Must be 0 or more'),
  has_help_debt: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

interface ManualEntryFormProps {
  onSubmit: (data: FinancialsInput) => Promise<void>;
  onCancel?: () => void;
  initialValues?: Partial<FormValues>;
}

export function ManualEntryForm({ onSubmit, onCancel, initialValues }: ManualEntryFormProps) {
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      revenue: initialValues?.revenue ?? 0,
      other_income: initialValues?.other_income ?? 0,
      cost_of_sales: initialValues?.cost_of_sales ?? 0,
      operating_expenses: initialValues?.operating_expenses ?? 0,
      payg_instalments: initialValues?.payg_instalments ?? 0,
      payg_withholding: initialValues?.payg_withholding ?? 0,
      franking_credits: initialValues?.franking_credits ?? 0,
      turnover: initialValues?.turnover ?? 0,
      has_help_debt: initialValues?.has_help_debt ?? false,
    },
  });

  const handleSubmit = async (values: FormValues) => {
    setSubmitting(true);
    try {
      const data: FinancialsInput = {
        income: {
          revenue: values.revenue,
          other_income: values.other_income,
        },
        expenses: {
          cost_of_sales: values.cost_of_sales,
          operating_expenses: values.operating_expenses,
        },
        credits: {
          payg_instalments: values.payg_instalments,
          payg_withholding: values.payg_withholding,
          franking_credits: values.franking_credits,
        },
        turnover: values.turnover || values.revenue + values.other_income,
        has_help_debt: values.has_help_debt,
      };
      await onSubmit(data);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">Enter Financials</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            {/* Income */}
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Income
              </p>
              <div className="grid grid-cols-2 gap-3">
                <CurrencyField form={form} name="revenue" label="Revenue" />
                <CurrencyField form={form} name="other_income" label="Other Income" />
              </div>
            </div>

            {/* Expenses */}
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Expenses
              </p>
              <div className="grid grid-cols-2 gap-3">
                <CurrencyField form={form} name="cost_of_sales" label="Cost of Sales" />
                <CurrencyField form={form} name="operating_expenses" label="Operating Expenses" />
              </div>
            </div>

            {/* Credits */}
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Tax Credits
              </p>
              <div className="grid grid-cols-3 gap-3">
                <CurrencyField form={form} name="payg_instalments" label="PAYG Instalments" />
                <CurrencyField form={form} name="payg_withholding" label="PAYG Withholding" />
                <CurrencyField form={form} name="franking_credits" label="Franking Credits" />
              </div>
            </div>

            {/* Turnover */}
            <CurrencyField form={form} name="turnover" label="Aggregated Turnover (for SBE test)" />

            {/* HELP debt */}
            <FormField
              control={form.control}
              name="has_help_debt"
              render={({ field }) => (
                <FormItem className="flex items-center gap-3">
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="!mt-0">Has HELP/HECS debt</FormLabel>
                </FormItem>
              )}
            />

            {/* Actions */}
            <div className="flex gap-2 pt-2">
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Calculating...' : 'Calculate Tax Position'}
              </Button>
              {onCancel && (
                <Button type="button" variant="ghost" onClick={onCancel}>
                  Cancel
                </Button>
              )}
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

function CurrencyField({
  form,
  name,
  label,
}: {
  form: ReturnType<typeof useForm<FormValues>>;
  name: keyof FormValues;
  label: string;
}) {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="text-xs">{label}</FormLabel>
          <FormControl>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                $
              </span>
              <Input
                type="number"
                step="0.01"
                className="pl-7 tabular-nums"
                {...field}
                value={typeof field.value === 'number' ? field.value : 0}
                onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
              />
            </div>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}
