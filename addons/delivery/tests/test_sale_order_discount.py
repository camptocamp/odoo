# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import RecordCapturer

from odoo.addons.delivery.tests.common import DeliveryCommon
from odoo.addons.sale.tests.common import SaleCommon


@tagged('post_install', '-at_install')
class TestSaleOrderDiscount(DeliveryCommon, SaleCommon):
    """Discounts from the discount wizard on orders with a delivery line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls._prepare_carrier(
            cls._prepare_carrier_product(taxes_id=[Command.clear()]),
            fixed_price=10.0,
        )
        cls.sale_order.set_delivery_line(cls.carrier, 10.0)
        cls.delivery_line = cls.sale_order.order_line.filtered('is_delivery')
        cls.product_lines = cls.sale_order.order_line - cls.delivery_line

    def test_sol_discount_skips_delivery_line(self):
        """A discount on all order lines leaves the shipping cost untouched.

        Scenario:
            1. Take an order with two products and a shipping cost.
            2. Apply a 10% discount on all order lines.
        Expected:
            - Both product lines get the 10% discount.
            - The shipping line gets no discount.
        """
        self.env['sale.order.discount'].create({
            'sale_order_id': self.sale_order.id,
            'discount_percentage': 0.1,
            'discount_type': 'sol_discount',
        }).action_apply_discount()

        self.assertEqual(self.product_lines.mapped('discount'), [10.0, 10.0])
        self.assertEqual(self.delivery_line.discount, 0.0)

    def test_so_discount_excludes_delivery_line_from_base(self):
        """A global discount is computed on the products only, not on the shipping cost.

        Scenario:
            1. Take an order with two products and a shipping cost.
            2. Apply a 10% global discount.
        Expected:
            - The discount amounts to 10% of the products, without the shipping cost.
        """
        products_amount = sum(self.product_lines.mapped('price_subtotal'))
        with RecordCapturer(self.env['sale.order.line']) as capture:
            self.env['sale.order.discount'].create({
                'sale_order_id': self.sale_order.id,
                'discount_percentage': 0.1,
                'discount_type': 'so_discount',
            }).action_apply_discount()

        self.assertAlmostEqual(capture.records.price_subtotal, -products_amount * 0.1)
