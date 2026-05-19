import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FilterBar from '../pages/Spend/FilterBar';

const OPTIONS = {
  months: [
    { month_key: 202601, month_label: 'Jan 2026' },
    { month_key: 202602, month_label: 'Feb 2026' },
  ],
  expense_types: ['Capex', 'Opex', 'Travel'],
  company_codes: ['1000', '2000'],
  oracle_departments: [
    { oracle_department: '1100', oracle_department_name: 'Engineering' },
    { oracle_department: '1200', oracle_department_name: 'Sales' },
  ],
  oracle_account_groups: ['R&D', 'S&M'],
  vendors: ['AWS', 'Zoom'],
  je_sources: ['Coupa', 'Manual'],
};

function renderFilterBar(activeFilters = {}, onFilterChange = vi.fn()) {
  return render(
    <FilterBar options={OPTIONS} activeFilters={activeFilters} onFilterChange={onFilterChange} />
  );
}

describe('FilterBar', () => {
  it('renders all 7 slicer dropdowns', () => {
    renderFilterBar();
    expect(screen.getByText('Month')).toBeInTheDocument();
    expect(screen.getByText('Expense Type')).toBeInTheDocument();
    expect(screen.getByText('Co. Code')).toBeInTheDocument();
    expect(screen.getByText('Oracle Dept')).toBeInTheDocument();
    expect(screen.getByText('Acct. Group')).toBeInTheDocument();
    expect(screen.getByText('Vendor')).toBeInTheDocument();
    expect(screen.getByText('JE Source')).toBeInTheDocument();
  });

  it('opens dropdown and shows options when trigger is clicked', async () => {
    renderFilterBar();
    const trigger = screen.getByText('Expense Type').closest('button');
    await userEvent.click(trigger);
    expect(screen.getByText('Capex')).toBeInTheDocument();
    expect(screen.getByText('Opex')).toBeInTheDocument();
    expect(screen.getByText('Travel')).toBeInTheDocument();
  });

  it('shows All checkbox at top of dropdown', async () => {
    renderFilterBar();
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    const allCheckboxes = screen.getAllByRole('checkbox');
    // first checkbox is "All"
    expect(allCheckboxes[0]).toBeChecked();
  });

  it('calls onFilterChange with selected value when checkbox is checked', async () => {
    const onFilterChange = vi.fn();
    renderFilterBar({}, onFilterChange);
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    await userEvent.click(screen.getByText('Capex'));
    expect(onFilterChange).toHaveBeenCalledWith({ expense_types: ['Capex'] });
  });

  it('calls onFilterChange removing value when already-selected checkbox is unchecked', async () => {
    const onFilterChange = vi.fn();
    renderFilterBar({ expense_types: ['Capex'] }, onFilterChange);
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    await userEvent.click(screen.getByText('Capex'));
    expect(onFilterChange).toHaveBeenCalledWith({ expense_types: [] });
  });

  it('shows count badge when items are selected', () => {
    renderFilterBar({ expense_types: ['Capex', 'Opex'] });
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('clicking All clears the selection', async () => {
    const onFilterChange = vi.fn();
    renderFilterBar({ expense_types: ['Capex'] }, onFilterChange);
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    await userEvent.click(screen.getAllByText('All')[0]);
    expect(onFilterChange).toHaveBeenCalledWith({ expense_types: [] });
  });

  it('shows Clear selection link in footer when items selected', async () => {
    renderFilterBar({ expense_types: ['Capex'] });
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    expect(screen.getByText('Clear selection')).toBeInTheDocument();
  });

  it('does not show Clear selection link when nothing is selected', async () => {
    renderFilterBar({});
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    expect(screen.queryByText('Clear selection')).not.toBeInTheDocument();
  });

  it('closes dropdown when clicking outside', async () => {
    renderFilterBar();
    await userEvent.click(screen.getByText('Expense Type').closest('button'));
    expect(screen.getByText('Capex')).toBeInTheDocument();
    await userEvent.click(document.body);
    expect(screen.queryByText('Capex')).not.toBeInTheDocument();
  });
});
