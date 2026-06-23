// UI Elements
export const els = {
    sessionInfo: document.getElementById('session-info'),
    fileUpload: document.getElementById('file-upload'),
    uploadStatus: document.getElementById('upload-status'),
    datasetDetails: document.getElementById('dataset-details'),
    detailDesc: document.getElementById('detail-desc'),
    groupColSelect: document.getElementById('group-col-select'),
    valueColSearch: document.getElementById('value-col-search'),
    valueColumnsList: document.getElementById('value-columns-list'),
    discreteColSearch: document.getElementById('discrete-col-search'),
    discreteColumnsList: document.getElementById('discrete-columns-list'),
    subgroupsSection: document.getElementById('subgroups-section'),
    subgroupsSearch: document.getElementById('subgroups-search'),
    subgroupsList: document.getElementById('subgroups-list'),
    btnStep1Next: document.getElementById('btn-step-1-next'),

    activeFilters: document.getElementById('active-filters'),
    filterType: document.getElementById('filter-type'),
    filterCol: document.getElementById('filter-col'),
    fieldsNumericRange: document.getElementById('fields-numeric_range'),
    fieldsCategoryFilter: document.getElementById('fields-category_filter'),
    filterNumMin: document.getElementById('filter-num-min'),
    filterNumMax: document.getElementById('filter-num-max'),
    filterCatValues: document.getElementById('filter-cat-values'),
    filterCatExclude: document.getElementById('filter-cat-exclude'),
    btnAddFilterAction: document.getElementById('btn-add-filter-action'),
    btnStep2Next: document.getElementById('btn-step-2-next'),

    methodsList: document.getElementById('methods-list'),
    btnStep3Next: document.getElementById('btn-step-3-next'),

    resultMethodName: document.getElementById('result-method-name'),
    resultStatistic: document.getElementById('result-statistic'),
    resultPValue: document.getElementById('result-p-value'),
    resultSummaryText: document.getElementById('result-summary-text'),
    plotsSigFilter: document.getElementById('plots-sig-filter'),
    filteredPlotsCounter: document.getElementById('filtered-plots-counter'),
    btnStep4Next: document.getElementById('btn-step-4-next'),

    plotsSelector: document.getElementById('plots-selector'),
    plotsDisplay: document.getElementById('plots-display'),
    btnGeneratePlots: document.getElementById('btn-generate-plots'),
    plotsGenerationCounter: document.getElementById('plots-generation-counter'),
    btnStep5Next: document.getElementById('btn-step-5-next'),

    btnExportDownload: document.getElementById('btn-export-download'),
    btnRestart: document.getElementById('btn-restart'),
    btnStep2Back: document.getElementById('btn-step-2-back'),
    btnStep3Back: document.getElementById('btn-step-3-back'),
    btnStep4Back: document.getElementById('btn-step-4-back'),
    btnStep5Back: document.getElementById('btn-step-5-back'),
    btnStep6Back: document.getElementById('btn-step-6-back'),

    errorToast: document.getElementById('error-toast'),
    toastMsg: document.getElementById('toast-msg'),
    btnToastClose: document.getElementById('btn-toast-close')
};

// Map step identifier strings to nav and panel elements
export const stepsConfig = [
    { key: 'dataset_selection', navId: 'nav-step-1', panelId: 'panel-step-1' },
    { key: 'filters', navId: 'nav-step-2', panelId: 'panel-step-2' },
    { key: 'stat_method', navId: 'nav-step-3', panelId: 'panel-step-3' },
    { key: 'results', navId: 'nav-step-4', panelId: 'panel-step-4' },
    { key: 'plot_selection', navId: 'nav-step-5', panelId: 'panel-step-5' },
    { key: 'export', navId: 'nav-step-6', panelId: 'panel-step-6' }
];
