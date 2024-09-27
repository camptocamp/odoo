odoo.define('website_event.website_event', function (require) {

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Widget = require('web.Widget');
    var core = require('web.core');
    var publicWidget = require('web.public.widget');
    const {ReCaptcha} = require('google_recaptcha.ReCaptchaV3');

    var _t = core._t;

    // Catch registration form event, because of JS for attendee details
    var EventRegistrationForm = Widget.extend({

        /**
         * @constructor
         */
        init: function () {
            this._super(...arguments);
            this._recaptcha = new ReCaptcha();
        },

        /**
         * @override
         */
        willStart: function () {
            this._recaptcha.loadLibs();
            return this._super(...arguments);
        },
        /**
        /**
         * @override
         */
        start: function () {
            var self = this;
            var res = this._super.apply(this, arguments).then(function () {
                $('#registration_form .a-submit')
                    .off('click')
                    .click(function (ev) {
                        self.on_click(ev);
                    })
                    .prop('disabled', false);
            });
            return res;
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * @private
         * @param {Event} ev
         */
        on_click: async function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var $form = $(ev.currentTarget).closest('form');
            var $button = $(ev.currentTarget).closest('[type="submit"]');
            var post = {};
            $('#registration_form table').siblings('.alert').remove();
            $('#registration_form select').each(function () {
                post[$(this).attr('name')] = $(this).val();
            });
            var tickets_ordered = _.some(_.map(post, function (value, key) { return parseInt(value); }));
            const tokenObj = await this._recaptcha.getToken('website_mass_mailing_subscribe');
            if (tokenObj.error) {
                core.bus.trigger('notification', {
                    type: 'danger',
                    title: _t("Error"),
                    message: tokenObj.error,
                    sticky: true,
                });
                return false;
            }
            if (!tickets_ordered) {
                $('<div class="alert alert-info"/>')
                    .text(_t('Please select at least one ticket.'))
                    .insertAfter('#registration_form table');
                return new Promise(function () {});
            } else {
                $button.attr('disabled', true);
                // Adding the recaptcha_token_response: tokenObj.token, to the post data
                post['recaptcha_token_response'] = tokenObj.token;
                var action = $form.data('action') || $form.attr('action');
                return ajax.jsonRpc(action, 'call', post).then(function (modal) {
                    let toastType = modal.toast_type;
                    var $modal = $(modal);
                    $modal.find('.modal-body > div').removeClass('container'); // retrocompatibility - REMOVE ME in master / saas-19
                    $modal.appendTo(document.body);
                    const modalBS = new Modal($modal[0], {backdrop: 'static', keyboard: false});
                    modalBS.show();
                    $modal.appendTo('body').modal('show');
                    $modal.on('click', '.js_goto_event', function () {
                        $modal.modal('hide');
                        $button.prop('disabled', false);
                    });
                    $modal.on('click', '.btn-close', function () {
                        $button.prop('disabled', false);
                    });
                    core.bus.trigger('notification', {
                        title: modal.title,
                        message: modal.message,
                        type: toastType,
                        sticky: true,
                    });
                });
            }
        },
    });

    publicWidget.registry.EventRegistrationFormInstance = publicWidget.Widget.extend({
        selector: '#registration_form',

        /**
         * @override
         */
        start: function () {
            var def = this._super.apply(this, arguments);
            this.instance = new EventRegistrationForm(this);
            return Promise.all([def, this.instance.attachTo(this.$el)]);
        },
        /**
         * @override
         */
        destroy: function () {
            this.instance.setElement(null);
            this._super.apply(this, arguments);
            this.instance.setElement(this.$el);
        },
    });

    return EventRegistrationForm;
    });
