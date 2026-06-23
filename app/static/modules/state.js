// Global State
export const state = {
    sessionId: null,
    currentStep: 'dataset_selection',
    selectedDatasetId: '',
    selectedDatasetColumns: [],
    selectedValueColumns: new Set(),
    selectedDiscreteColumns: new Set(),
    selectedGroups: new Set(),
    availableGroups: [],
    activeFilters: [],
    applicableMethods: [],
    selectedMethod: '',
    selectedDiscreteMethod: '',
    applicablePlots: [],
    selectedPlots: [],
    selectedExportFormat: 'pdf',
    statResults: [],
    plotsTopN: 1,
    sortColumn: null,
    sortAsc: true
};
