// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

define([
    'jquery',
    'require',
    './toolbar',
    './celltoolbar',
    'base/js/i18n'
], function($, requirejs, toolbar, celltoolbar, i18n) {
    "use strict";

    var MainToolBar = function (selector, options) {
        /**
         * Constructor
         *
         * Parameters:
         *  selector: string
         *  options: dictionary
         *      Dictionary of keyword arguments.
         *          events: $(Events) instance
         *          notebook: Notebook instance
         **/
        toolbar.ToolBar.apply(this, [selector, options] );
        this.events = options.events;
        this.notebook = options.notebook;
        this._make();
        Object.seal(this);
    };

    MainToolBar.prototype = Object.create(toolbar.ToolBar.prototype);

    const operateGroup = [
        'jupyter-notebook:save-notebook',
        'jupyter-notebook:run-cell',
        'jupyter-notebook:run-all-cells',
        // 'jupyter-notebook:show-all-run-time',
        // 'jupyter-notebook:hide-all-run-time',
        'jupyter-notebook:version-management',
        // 'jupyter-notebook:upload-file',
        'jupyter-notebook:notebook-report'
    ];

    !window.git_available && operateGroup.splice(3, 1); // 如果全局禁用版本管理，去除版本管理的按钮
    MainToolBar.prototype._make = function () {
        var grps = [
            [
                [ 
                    { action: 'jupyter-notebook:insert-cell-code', label: i18n.msg._('Code') }, 
                    { action: 'jupyter-notebook:insert-cell-markdown', label: i18n.msg._('Text') }
                ],
                'insert_below_with_type'
            ],
            [
                operateGroup,
                'step_action_sections'
            ]
        ];
        this.construct(grps);
    };

    MainToolBar.prototype._pseudo_actions = {};

    MainToolBar.prototype._pseudo_actions.add_cpu_RAM_cell = function () {
        const that = this;
        const leftIcon = $('<div></div>')
                        .addClass('fa fa-check')
                        .attr('style', 'color: rgba(63,192,109,1);width: 16px; height: 16px;');
        const rightSection = $('<div></div>');
        const section = $('<div></div>')
                        .addClass('notebook-cup-crm')
                        .attr('style', 'width: 120px;display:inline-block; font-size: 12px;')
                        .append(leftIcon)
                        .append(rightSection);
        that.notebook.keyboard_manager.register_events(section);
        return section;
    };

    // add a cell type drop down to the maintoolbar.
    // triggered when the pseudo action `<add_celltype_list>` is
    // encountered when building a toolbar.
    MainToolBar.prototype._pseudo_actions.add_celltype_list = function () {
        var that = this;
        var multiselect = $('<option/>').attr('value','multiselect').attr('disabled','').text('-');
        var sel = $('<select/>')
            .attr('id','cell_type')
            .attr('aria-label', i18n.msg._('combobox, select cell type'))
            .attr('role', 'combobox')
            .addClass('form-control select-xs')
            .append($('<option/>').attr('value','code').text('Code'))
            .append($('<option/>').attr('value','markdown').text('Markdown'))
            .append(multiselect);
        this.notebook.keyboard_manager.register_events(sel);
        this.events.on('selected_cell_type_changed.Notebook', function (event, data) {
            if (data.editable === false) {
                sel.attr('disabled', true);
            } else {
                sel.removeAttr('disabled');
            }
            /**
             * 与父级通讯，调用外部方法
             */
            window.parent.postMessage({
                selected: data.cell_type,
                notebook_id: window.__notebook_id__,
                eventType: 'languageChanged'
            }, '*');

            if (that.notebook.get_selected_cells_indices().length > 1) {
                multiselect.show();
                sel.val('multiselect');
            } else {
                multiselect.hide();
                if (data.cell_type === 'heading') {
                    sel.val('Markdown');
                } else {
                    sel.val(data.cell_type);
                }
            }
        });
        sel.change(function () {
            var cell_type = $(this).val();
            switch (cell_type) {
            case 'code':
                that.notebook.cells_to_code();
                break;
            case 'markdown':
                that.notebook.cells_to_markdown();
                break;
            case 'raw':
                that.notebook.cells_to_raw();
                break;
            case 'heading':
                that.notebook._warn_heading();
                that.notebook.to_heading();
                sel.val('markdown');
                break;
            case 'multiselect':
                break;
            default:
                console.log(i18n.msg._("unrecognized cell type:"), cell_type);
            }
            that.notebook.focus_cell();
        });
        return sel;

    };

    return {'MainToolBar': MainToolBar};
});
