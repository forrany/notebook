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

    var CellFixedToolBar = function (selector, options) {
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
        this.render_default = !!options.render_default;
        this.render_default && this._make();
        Object.seal(this);
    };

    CellFixedToolBar.prototype = Object.create(toolbar.ToolBar.prototype);
    CellFixedToolBar.prototype.customCells = function (grps) {
        grps && this.construct(grps);
    }

    CellFixedToolBar.prototype._make = function () {
        var grps = [
            [
                ['jupyter-notebook:move-cell-up',
                'jupyter-notebook:move-cell-down'
                ],
                'move_up_down'
            ],
            [
                ['jupyter-notebook:delete-cell'],
                'delete-cell'
            ],
            [
                ['jupyter-notebook:cut-cell',
                'jupyter-notebook:copy-cell',
                'jupyter-notebook:paste-cell-below'
                ] ,
                'cut_copy_paste'
            ]
    ];
        this.construct(grps);
    };

    CellFixedToolBar.prototype._pseudo_actions = {};
    return {'CellFixedToolBar': CellFixedToolBar};
});
