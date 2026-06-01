import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SpendTable from '../pages/Spend/SpendTable';

const DEFAULT_FILTERS = { sort_by: 'month_key', sort_order: 'desc', page: 1, page_size: 50 };

function makeRow(overrides = {}) {
  return {
    id: 1,
    month_key: 202601,
    month_label: 'Jan 2026',
    expense_type: 'Opex',
    company_code: '1000',
    oracle_organization: 'US01',
    oracle_account_number: 'ACC-1001',
    oracle_department: '1100',
    oracle_department_name: 'Engineering',
    oracle_cost_center_hierarchy: 'Americas > US',
    oracle_account_group: 'R&D',
    oracle_account_sub_group: 'Engineering Salaries',
    oracle_cost_element: 'Salaries',
    line_desc: 'Monthly subscription',
    vendor_name: 'AWS',
    po_recon: null,
    po_description: null,
    purchase_order_number: null,
    purchase_order_line_number: null,
    invoice_number: null,
    invoice_line_number: null,
    je_source: 'Coupa',
    amount_usd: '1234.56',
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...overrides,
  };
}

function makePaginatedData(items, overrides = {}) {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 50,
    total_pages: 1,
    ...overrides,
  };
}

function renderTable(props = {}) {
  const defaults = {
    data: undefined,
    loading: false,
    fetching: false,
    isError: false,
    filters: DEFAULT_FILTERS,
    onPageChange: vi.fn(),
    onSort: vi.fn(),
  };
  return render(<SpendTable {...defaults} {...props} />);
}

describe('SpendTable', () => {
  describe('column headers', () => {
    it('renders group header "Oracle"', () => {
      renderTable();
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });

    it('renders group header "Oracle Dept"', () => {
      renderTable();
      expect(screen.getByText('Oracle Dept')).toBeInTheDocument();
    });

    it('renders group header "Oracle Account"', () => {
      renderTable();
      expect(screen.getByText('Oracle Account')).toBeInTheDocument();
    });

    it('renders leaf column headers', () => {
      renderTable();
      expect(screen.getByText('Month')).toBeInTheDocument();
      expect(screen.getByText('Vendor')).toBeInTheDocument();
      expect(screen.getByText('$')).toBeInTheDocument();
      expect(screen.getByText('JE Source')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows skeleton rows when loading', () => {
      const { container } = renderTable({ loading: true });
      const skeletons = container.querySelectorAll('.animate-pulse td');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('shows refreshing indicator when fetching but not loading', () => {
      renderTable({ fetching: true, loading: false, data: makePaginatedData([]) });
      expect(screen.getByText('Refreshing')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when isError is true', () => {
      renderTable({ isError: true });
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows no-records message when data is empty', () => {
      renderTable({ data: makePaginatedData([]) });
      expect(screen.getByText(/no records match/i)).toBeInTheDocument();
    });
  });

  describe('data rendering', () => {
    it('renders a row with correct vendor name', () => {
      renderTable({ data: makePaginatedData([makeRow({ vendor_name: 'Zoom' })]) });
      expect(screen.getByText('Zoom')).toBeInTheDocument();
    });

    it('formats amount as currency', () => {
      renderTable({ data: makePaginatedData([makeRow({ amount_usd: '1234.56' })]) });
      expect(screen.getByText('$1,234.56')).toBeInTheDocument();
    });

    it('renders month label not month key', () => {
      renderTable({ data: makePaginatedData([makeRow()]) });
      expect(screen.getByText('Jan 2026')).toBeInTheDocument();
      expect(screen.queryByText('202601')).not.toBeInTheDocument();
    });

    it('renders null optional fields as dash', () => {
      renderTable({ data: makePaginatedData([makeRow({ po_recon: null })]) });
      const dashes = screen.getAllByText('–');
      expect(dashes.length).toBeGreaterThan(0);
    });

    it('renders multiple rows', () => {
      renderTable({
        data: makePaginatedData([
          makeRow({ id: 1, vendor_name: 'AWS' }),
          makeRow({ id: 2, vendor_name: 'Zoom' }),
          makeRow({ id: 3, vendor_name: 'Figma' }),
        ]),
      });
      expect(screen.getByText('AWS')).toBeInTheDocument();
      expect(screen.getByText('Zoom')).toBeInTheDocument();
      expect(screen.getByText('Figma')).toBeInTheDocument();
    });
  });

  describe('sorting', () => {
    it('calls onSort with toggled direction when clicking active sort column', async () => {
      const onSort = vi.fn();
      // currently sorted by month_key desc
      renderTable({ filters: { ...DEFAULT_FILTERS, sort_by: 'amount_usd', sort_order: 'asc' }, onSort });
      await userEvent.click(screen.getByText('$').closest('th'));
      expect(onSort).toHaveBeenCalledWith('amount_usd', 'desc');
    });

    it('calls onSort asc when clicking an inactive column', async () => {
      const onSort = vi.fn();
      renderTable({ onSort });
      await userEvent.click(screen.getByText('Vendor').closest('th'));
      expect(onSort).toHaveBeenCalledWith('vendor_name', 'asc');
    });
  });

  describe('pagination', () => {
    it('does not show pagination for single page', () => {
      renderTable({ data: makePaginatedData([makeRow()], { total_pages: 1 }) });
      expect(screen.queryByText('← Prev')).not.toBeInTheDocument();
    });

    it('shows pagination when total_pages > 1', () => {
      renderTable({
        data: makePaginatedData([makeRow()], { total: 100, total_pages: 2, page: 1 }),
      });
      expect(screen.getByText('← Prev')).toBeInTheDocument();
      expect(screen.getByText('Next →')).toBeInTheDocument();
    });

    it('calls onPageChange when Next is clicked', async () => {
      const onPageChange = vi.fn();
      renderTable({
        data: makePaginatedData([makeRow()], { total: 100, total_pages: 3, page: 1 }),
        onPageChange,
      });
      await userEvent.click(screen.getByText('Next →'));
      expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it('prev button is disabled on first page', () => {
      renderTable({
        data: makePaginatedData([makeRow()], { total: 100, total_pages: 2, page: 1 }),
      });
      expect(screen.getByText('← Prev')).toBeDisabled();
    });
  });
});
