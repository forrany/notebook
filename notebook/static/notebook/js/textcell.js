// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

define([
    'jquery',
    'base/js/utils',
    'base/js/i18n',
    'notebook/js/cell',
    'base/js/security',
    'services/config',
    'notebook/js/mathjaxutils',
    'notebook/js/celltoolbar',
    'components/marked/lib/marked',
    'codemirror/lib/codemirror',
    'codemirror/mode/gfm/gfm',
    'notebook/js/codemirror-ipythongfm',
    'notebook/js/cellfixedtoolbar'
], function(
    $,
    utils,
    i18n,
    cell,
    security,
    configmod,
    mathjaxutils,
    celltoolbar,
    marked,
    CodeMirror,
    gfm,
    ipgfm,
    cellfixedtoolbar
    ) {
    "use strict";
    function encodeURIandParens(uri){return encodeURI(uri).replace('(','%28').replace(')','%29');}

    var Cell = cell.Cell;

    var TextCell = function (options) {
        /**
         * Constructor
         *
         * Construct a new TextCell, codemirror mode is by default 'htmlmixed', 
         * and cell type is 'text' cell start as not redered.
         *
         * Parameters:
         *  options: dictionary
         *      Dictionary of keyword arguments.
         *          events: $(Events) instance 
         *          config: dictionary
         *          keyboard_manager: KeyboardManager instance 
         *          notebook: Notebook instance
         */
        options = options || {};

        // in all TextCell/Cell subclasses
        // do not assign most of members here, just pass it down
        // in the options dict potentially overwriting what you wish.
        // they will be assigned in the base class.
        this.notebook = options.notebook;
        this.events = options.events;
        this.config = options.config;
        this.actions_toolbar = null;

        // we cannot put this as a class key as it has handle to "this".
        Cell.apply(this, [{
                    config: options.config, 
                    keyboard_manager: options.keyboard_manager, 
                    events: this.events}]);

        this.cell_type = this.cell_type || 'text';
        mathjaxutils = mathjaxutils;
        this.rendered = false;
    };

    TextCell.prototype = Object.create(Cell.prototype);

    TextCell.options_default = {
        cm_config : {
            mode: 'htmlmixed',
            lineWrapping : true,
        }
    };


    /**
     * Create the DOM element of the TextCell
     * @method create_element
     * @private
     */
    TextCell.prototype.create_element = function () {
        Cell.prototype.create_element.apply(this, arguments);
        var that = this;

        var cell = $("<div>").addClass('cell text_cell');
        cell.attr('tabindex','2');
        var prompt_container = $('<div/>').addClass('prompt_container');
        var run_this_cell = $('<div></div>').addClass('run_this_cell');
        run_this_cell.prop('title', 'Run this cell');
        run_this_cell.append('<i class="icon-play-6"></i>');
        run_this_cell.click(function (event) {
            event.stopImmediatePropagation();
            that.execute();
        });

        var prompt = $('<div/>').addClass('prompt input_prompt');
        var prompt_container = $('<div/>').addClass('prompt_container');
        var run_this_cell = $('<div></div>').addClass('run_this_cell');
        run_this_cell.prop('title', 'Run this cell');
        run_this_cell.append('<i class="icon-play-6"></i>');
        run_this_cell.click(function (event) {
            event.stopImmediatePropagation();
            that.execute();
        });

        prompt_container.append(prompt).append(run_this_cell);
    
        cell.append(prompt_container);
        var inner_cell = $('<div/>').addClass('inner_cell');
        this.celltoolbar = new celltoolbar.CellToolbar({
            cell: this, 
            notebook: this.notebook});
        inner_cell.append(this.celltoolbar.element);
        var input_area = $('<div/>').addClass('input_area').attr("aria-label", i18n.msg._("Edit Markup Text here"));
        var markdown_wrapper = $('<textarea/>').addClass('markdown_editor');
        input_area.append(markdown_wrapper);
        this.markdown_editor = Mditor.fromTextarea(markdown_wrapper.get(0));
        
        /**
         * In case of bugs that put the keyboard manager into an inconsistent state,
         * ensure KM is enabled when CodeMirror is focused
         * 
         * 聚焦时，将mode变为edit，全局的键盘事件改变
         * 失去焦点时，mode为command，键盘事件由notebook接管
         * keydown时，触发keyevnet，keyevent内部会根据mode来做相关判定
         * 
         */
        this.markdown_editor.on('ready', function() {
            input_area.find('.textarea').on('focus', function () {
                that.events.trigger('edit_mode.Cell', {cell: that});
                if (that.keyboard_manager) {
                    that.keyboard_manager.enable();
                }
            }).on('blur', function(cm, change) {
                setTimeout(() => {
                    if (!that.selected) { // 如果已经没有被选择，说明点击了其他Cell
                        that.events.trigger('command_mode.Cell', {cell: that});
                        that.execute();
                    }
                }, 100);
            }).on('keydown', $.proxy(this.handle_keyevent,this));
            that.markdown_editor.focus();
        });

        // The tabindex=-1 makes this div focusable.
        var render_area = $('<div/>').addClass('text_cell_render rendered_html')
            .attr('tabindex','-1');
        inner_cell.append(input_area).append(render_area);
        cell.append(inner_cell);


        const action_bar_container = $('<div></div>');
        this.cellfixedtoolbar = new cellfixedtoolbar.CellFixedToolBar(action_bar_container, {
            notebook: this.notebook,
            events: this.keyboard_manager.events,
            actions: this.keyboard_manager.actions,
            render_default: true
        });
        cell.append(action_bar_container);
        
        const btns = [{
            label: i18n.msg._('Code'),
            icon: 'icon-add-9',
            cell_type: 'code'
        }, {
            label: i18n.msg._('Text'),
            icon: 'icon-add-9',
            cell_type: 'markdown'
        }];
        const btn_group = $('<div></div>').addClass('btn-group');
        for (let i = 0; i < btns.length; i++) {
            var button  = $('<button/>')
                .addClass('btn btn-default')
                .attr("title", i18n.msg._(btns[i].label))
                .attr("data-toggle", "tooltip")
                .append(
                    $("<i/>").addClass(btns[i].icon).addClass('fa')
                )
                .append(
                    $('<span/>').text(i18n.msg._(btns[i].label)).addClass('toolbar-btn-label')
                );
            button.click(function () {
                const index = that.notebook.find_cell_index(that);
                that.notebook.insert_cell_below(btns[i].cell_type, index);
                that.notebook.select(index + 1, true);
                that.notebook.focus_cell();
            });
            btn_group.append(button);
        }
        const bottom_hover_bars = $('<div></div>')
            .addClass('cell-empty-hover cell-insert-bar')
            .append(btn_group);

        cell.append(bottom_hover_bars);
        this.element = cell;
        this.inner_cell = inner_cell;
    };


    // Cell level actions

    TextCell.prototype.add_attachment = function (key, mime_type, b64_data) {
        /**
         * Add a new attachment to this cell
         */
        this.attachments[key] = {};
        this.attachments[key][mime_type] = b64_data;
    };

    TextCell.prototype.select = function () {
        var cont = Cell.prototype.select.apply(this, arguments);
        if (cont) {
        }
        return cont;
    };

    TextCell.prototype.unrender = function () {
        var cont = Cell.prototype.unrender.apply(this);
        if (cont) {
            var text_cell = this.element;
            if (this.get_text() === this.placeholder) {
                this.set_text('');
            }
            this.refresh();
        }
        return cont;
    };

    TextCell.prototype.execute = function () {
        this.render();
    };

    /**
     * setter: {{#crossLink "TextCell/set_text"}}{{/crossLink}}
     * @method get_text
     * @return {string} CodeMirror current text value
     */
    TextCell.prototype.get_text = function() {
        return this.markdown_editor.value;
    };

    /**
     * @param {string} text - Codemiror text value
     * @see TextCell#get_text
     * @method set_text
     * */
    TextCell.prototype.set_text = function(text) {
        this.markdown_editor.value = text;
        this.unrender();
    };

    /**
     * setter :{{#crossLink "TextCell/set_rendered"}}{{/crossLink}}
     * @method get_rendered
     * */
    TextCell.prototype.get_rendered = function() {
        return this.element.find('div.text_cell_render').html();
    };

    /**
     * @method set_rendered
     */
    TextCell.prototype.set_rendered = function(text) {
        this.element.find('div.text_cell_render').html(text);
    };


    /**
     * Create Text cell from JSON
     * @param {json} data - JSON serialized text-cell
     * @method fromJSON
     */
    TextCell.prototype.fromJSON = function (data) {
        Cell.prototype.fromJSON.apply(this, arguments);
        if (data.cell_type === this.cell_type) {
            if (data.attachments !== undefined) {
                this.attachments = data.attachments;
            }

            if (data.source !== undefined) {
                this.set_text(data.source);
                // make this value the starting point, so that we can only undo
                // to this state, instead of a blank cell
                // this.code_mirror.clearHistory();
                // TODO: This HTML needs to be treated as potentially dangerous
                // user input and should be handled before set_rendered.
                this.set_rendered(data.rendered || '');
                this.rendered = false;
                this.render();
            }
        }
    };

    /** Generate JSON from cell
     * @param {bool} gc_attachments - If true, will remove unused attachments
     *               from the returned JSON
     * @return {object} cell data serialised to json
     */
    TextCell.prototype.toJSON = function (gc_attachments) {
        if (gc_attachments === undefined) {
            gc_attachments = false;
        }

        var data = Cell.prototype.toJSON.apply(this);
        data.source = this.get_text();
        if (data.source == this.placeholder) {
            data.source = "";
        }

        // We deepcopy the attachments so copied cells don't share the same
        // objects
        if (Object.keys(this.attachments).length > 0) {
            if (gc_attachments) {
                // Garbage collect unused attachments : The general idea is to
                // render the text, and find used attachments like when we
                // substitute them in render()
                var that = this;
                data.attachments = {};
                // To find attachments, rendering to HTML is easier than
                // searching in the markdown source for the multiple ways you
                // can reference an image in markdown (using []() or a
                // HTML <img>)
                var text = this.get_text();
                marked(text, function (err, html) {
                    html = $(security.sanitize_html_and_parse(html));
                    html.find('img[src^="attachment:"]').each(function (i, h) {
                        h = $(h);
                        var key = h.attr('src').replace(/^attachment:/, '');
                        if (that.attachments.hasOwnProperty(key)) {
                            data.attachments[key] = JSON.parse(JSON.stringify(
                                that.attachments[key]));
                        }

                        // This is to avoid having the browser do a GET request
                        // on the invalid attachment: URL
                        h.attr('src', '');
                    });
                });
                if (data.attachments.length === 0) {
                    // omit attachments dict if no attachments
                    delete data.attachments;
                }
            } else {
                data.attachments = JSON.parse(JSON.stringify(this.attachments));
            }
        }
        return data;
    };


    var MarkdownCell = function (options) {
        /**
         * Constructor
         *
         * Parameters:
         *  options: dictionary
         *      Dictionary of keyword arguments.
         *          events: $(Events) instance 
         *          config: ConfigSection instance
         *          keyboard_manager: KeyboardManager instance 
         *          notebook: Notebook instance
         */
        options = options || {};
        var config_default = utils.mergeopt(TextCell, MarkdownCell.options_default);
        this.class_config = new configmod.ConfigWithDefaults(options.config,
                                            config_default, 'MarkdownCell');
        this.cell_type = 'markdown';

        // Used to keep track of drag events
        this.drag_counter = 0;

        TextCell.apply(this, [$.extend({}, options, {config: options.config})]);
    };

    MarkdownCell.options_default = {
        cm_config: {
            mode: 'ipythongfm'
        },
        placeholder: "Type *Markdown* and LaTeX: $\\alpha^2$"
    };

    MarkdownCell.prototype = Object.create(TextCell.prototype);

    MarkdownCell.prototype.set_heading_level = function (level) {
        /**
         * make a markdown cell a heading
         */
        level = level || 1;
        var source = this.get_text();
        source = source.replace(/^(#*)\s?/,
            new Array(level + 1).join('#') + ' ');
        this.set_text(source);
        this.refresh();
        if (this.rendered) {
            this.render();
        }
    };

    MarkdownCell.prototype.select = function () {
        var cont = TextCell.prototype.select.apply(this, arguments);
        if (cont) {
            this.notebook.set_insert_image_enabled(!this.rendered);
        }
    };

    MarkdownCell.prototype.unrender = function () {
        var cont = TextCell.prototype.unrender.apply(this);
        this.notebook.set_insert_image_enabled(true);
    };

    MarkdownCell.prototype.insert_inline_image_from_blob = function(blob) {
        /**
         * Insert markup for an inline image at the current cursor position.
         * This works as follow :
         * - We insert the base64-encoded blob data into the cell attachments
         *   dictionary, keyed by the filename.
         * - We insert an img tag with a 'attachment:key' src that refers to
         *   the attachments entry.
         *
         * Parameters:
         *  file: Blob
         *      The JS Blob object (e.g. from the DataTransferItem)
         */
        var that = this;
        var pos = this.code_mirror.getCursor();
        var reader = new FileReader();
        // We can get either a named file (drag'n'drop) or a blob (copy/paste)
        // We generate names for blobs
        var key;
        if (blob.name !== undefined) {
            key = encodeURIandParens(blob.name);
        } else {
            key = '_auto_' + Object.keys(that.attachments).length;
        }

        reader.onloadend = function() {
            var d = utils.parse_b64_data_uri(reader.result);
            if (blob.type != d[0]) {
                // TODO(julienr): Not sure what we should do in this case
                console.log('File type (' + blob.type + ') != data-uri ' +
                            'type (' + d[0] + ')');
            }
            that.add_attachment(key, blob.type, d[1]);
            var img_md = '![' + key + '](attachment:' + key + ')';
            that.code_mirror.replaceRange(img_md, pos);
        };
        reader.readAsDataURL(blob);
    };

    /**
     * @method render
     */
    MarkdownCell.prototype.render = function () {
        // We clear the dropzone here just in case the dragenter/leave
        // logic of bind_events wasn't 100% successful.
        this.drag_counter = 0;
        this.inner_cell.removeClass('dropzone');

        var cont = TextCell.prototype.render.apply(this);
        if (cont) {
            var that = this;
            var text = this.get_text();
            var math = null;
            if (text === "") { text = this.placeholder; }
            var text_and_math = mathjaxutils.remove_math(text);
            text = text_and_math[0];
            math = text_and_math[1];

            // 使标题解析 # 号可以无空格
            marked.Lexer.rules.gfm.heading = marked.Lexer.rules.heading;
            marked.Lexer.rules.tables.heading = marked.Lexer.rules.heading;

            var renderer = new marked.Renderer();
            // Prevent marked from returning inline styles for table cells
            renderer.tablecell = function (content, flags) {
              var type = flags.header ? 'th' : 'td';
              var style = flags.align == null ? '': ' style="text-align: ' + flags.align + '"';
              var start_tag = '<' + type + style + '>';
              var end_tag = '</' + type + '>\n';
              return start_tag + content + end_tag;
            };
            marked(text, { renderer: renderer, gfm: true, tables: true, breaks: true, pedantic: false,
                sanitize: false,
                smartLists: true,
                smartypants: false,
                mangle: false }, function (err, html) {
                html = mathjaxutils.replace_math(html, math);
                html = $(security.sanitize_html_and_parse(html));
                // add anchors to headings
                html.find(":header").addBack(":header").each(function (i, h) {
                    h = $(h);
                    var hash = h.text().replace(/ /g, '-');
                    h.attr('id', hash);
                    h.append(
                        $('<a/>')
                            .addClass('anchor-link')
                            .attr('href', '#' + hash)
                            .text('¶')
                            .on('click',function(){
                                setTimeout(function(){that.unrender(); that.render();}, 100);
                            })
                    );
                });
                // links in markdown cells should open in new tabs
                html.find("a[href]").not('[href^="#"]').attr("target", "_blank");
                // replace attachment:<key> by the corresponding entry
                // in the cell's attachments
                html.find('img[src^="attachment:"]').each(function (i, h) {
                  h = $(h);
                  var key = h.attr('src').replace(/^attachment:/, '');

                  if (that.attachments.hasOwnProperty(key)) {
                    var att = that.attachments[key];
                    var mime = Object.keys(att)[0];
                    h.attr('src', 'data:' + mime + ';base64,' + att[mime]);
                  } else {
                    h.attr('src', '');
                  }
                });
                that.set_rendered(html);
                that.typeset();
                that.events.trigger("rendered.MarkdownCell", {cell: that});
            });
        }
        return cont;
    };

    /** @method bind_events **/
    MarkdownCell.prototype.bind_events = function () {
        TextCell.prototype.bind_events.apply(this);
        var that = this;

        this.element.dblclick(function () {
            that.unrender();
            that.markdown_editor.focus();
        });
    };


    var RawCell = function (options) {
        /**
         * Constructor
         *
         * Parameters:
         *  options: dictionary
         *      Dictionary of keyword arguments.
         *          events: $(Events) instance 
         *          config: ConfigSection instance
         *          keyboard_manager: KeyboardManager instance 
         *          notebook: Notebook instance
         */
        options = options || {};
        var config_default = utils.mergeopt(TextCell, RawCell.options_default);
        this.class_config = new configmod.ConfigWithDefaults(options.config,
                                            config_default, 'RawCell');
        TextCell.apply(this, [$.extend({}, options, {config: options.config})]);
        this.cell_type = 'raw';
    };

    RawCell.options_default = {
        highlight_modes : {
            'diff'         :{'reg':[/^diff/]}
        },
        placeholder : i18n.msg._("Write raw LaTeX or other formats here, for use with nbconvert. " +
            "It will not be rendered in the notebook. " +
            "When passing through nbconvert, a Raw Cell's content is added to the output unmodified."),
    };

    RawCell.prototype = Object.create(TextCell.prototype);

    /** @method bind_events **/
    RawCell.prototype.bind_events = function () {
        TextCell.prototype.bind_events.apply(this);
        var that = this;
        this.element.focusout(function() {
            that.auto_highlight();
            that.render();
        });

        this.code_mirror.on('focus', function() { that.unrender(); });
    };

    /** @method render **/
    RawCell.prototype.render = function () {
        var cont = TextCell.prototype.render.apply(this);
        if (cont){
            var text = this.get_text();
            if (text === "") { text = this.placeholder; }
            this.set_text(text);
            this.element.removeClass('rendered');
            this.auto_highlight();
        }
        return cont;
    };

    var textcell = {
        TextCell: TextCell,
        MarkdownCell: MarkdownCell,
        RawCell: RawCell
    };
    return textcell;
});
