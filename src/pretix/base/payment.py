from decimal import Decimal

from django.forms import Form
from django.template import Context
from django.template.loader import get_template

from pretix.base.settings import SettingsSandbox


class BasePaymentProvider:
    """
    This is the base class for all payment providers.
    """

    def __init__(self, event):
        self.event = event
        self.settings = SettingsSandbox('payment', self.identifier, event)

    def __str__(self):
        return self.identifier

    @property
    def is_enabled(self):
        """
        Returns, whether or whether not this payment provider is enabled.
        By default, this is determined by the value of a setting.
        """
        return self.settings.get('_enabled', as_type=bool)

    def calculate_fee(self, price):
        """
        Calculate the fee for this payment provider which will be added to
        the final price if the price before fees (but after taxes) is 'price'.
        """
        fee_abs = self.settings.get('_fee_abs', as_type=Decimal, default=0)
        fee_percent = self.settings.get('_fee_percent', as_type=Decimal, default=0)
        return price * fee_percent / 100 + fee_abs

    @property
    def verbose_name(self) -> str:
        """
        A human-readable name for this payment provider
        """
        raise NotImplementedError()  # NOQA

    @property
    def identifier(self) -> str:
        """
        A unique identifier for this payment provider
        """
        raise NotImplementedError()  # NOQA

    @property
    def settings_form_fields(self) -> dict:
        """
        A dictionary. The keys should be (unprefixed) EventSetting keys,
        the values should be corresponding django form fields.

        We suggest returning a collections.OrderedDict object instead of a dict.
        """
        raise NotImplementedError()  # NOQA

    @property
    def checkout_form_fields(self) -> dict:
        """
        A dictionary. The keys should be unprefixed field names,
        the values should be corresponding django form fields.

        We suggest returning a collections.OrderedDict object instead of a dict.
        """
        # TODO: Proper handling of required=True fields in HTML
        return {}

    def checkout_form(self, request) -> Form:
        """
        Returns the Form object of the form that should be displayed when the
        user selects this provider as his payment method.
        """
        form = Form(
            data=(request.POST if request.method == 'POST' else None),
            prefix='payment_%s' % self.identifier,
            initial={
                k.replace('payment_%s_' % self.identifier, ''): v
                for k, v in request.session.items()
                if k.startswith('payment_%s_' % self.identifier)
            }
        )
        form.fields = self.checkout_form_fields
        return form

    def checkout_form_render(self, request) -> str:
        """
        Returns the HTML of the form that should be displayed when the user
        selects this provider as his payment method.
        """
        form = self.checkout_form(request)
        template = get_template('pretixpresale/event/checkout_payment_form_default.html')
        ctx = Context({'request': request, 'form': form})
        return template.render(ctx)

    def checkout_confirm_render(self, request) -> str:
        """
        Returns the HTML that should be displayed when the user selected this provider
        on the 'confirm order' page.
        """
        raise NotImplementedError()  # NOQA

    def checkout_prepare(self, request, total) -> "bool|HttpResponse":
        """
        Will be called if the user selects this provider as his payment method.
        If the payment provider provides a form to the user to enter payment data,
        this method should at least store the user's input into his session.

        It should return True or False, depending of the validity of the user's input,
        if the frontend should continue with default behaviour, or a redirect URL,
        if you need special behaviour.

        On errors, it should use Django's message framework to display an error message
        to the user (or the normal form validation error messages).

        :param total: The total price of the order, including the payment method fee.
        """
        form = self.checkout_form(request)
        if form.is_valid():
            for k, v in form.cleaned_data.items():
                request.session['payment_%s_%s' % (self.identifier, k)] = v
            return True
        else:
            return False

    def checkout_is_valid_session(self, request) -> bool:
        """
        This is called at the time the user tries to place the order. It should return
        True, if the user's session is valid and all data your payment provider requires
        in future steps is present.
        """
        raise NotImplementedError()  # NOQA

    def checkout_perform(self, request, order) -> str:
        """
        Will be called if the user submitted his order successfully to initiate the
        payment process.

        It should return a custom redirct URL, if you need special behaviour, or None to
        continue with default behaviour.

        On errors, it should use Django's message framework to display an error message
        to the user (or the normal form validation error messages).

        :param order: The order object
        """
        return None

    def order_pending_render(self, request, order) -> str:
        """
        Will be called if the user views the detail page of an unpaid order which is
        associated with this payment provider.

        It should return HTML code which should be displayed to the user. It should contian
        instructions on how to continue with the payment process, either in form of text
        or buttons/links/etc.

        :param order: The order object
        """
        raise NotImplementedError()  # NOQA

    def order_paid_render(self, request, order) -> str:
        """
        Will be called if the user views the detail page of an paid order which is
        associated with this payment provider.

        It should return HTML code which should be displayed to the user or None,
        if there is nothing to say.

        :param order: The order object
        """
        return None