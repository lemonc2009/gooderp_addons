# -*- coding: utf-8 -*-

from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class sell_receipt_wizard(models.TransientModel):
    _name = 'sell.receipt.wizard'
    _description = u'销售收款一览表向导'

    @api.model
    def _default_date_start(self):
        return self.env.user.company_id.start_date

    @api.model
    def _default_date_end(self):
        return date.today()

    date_start = fields.Date(u'开始日期', default=_default_date_start,
                             help=u'报表汇总的开始日期，默认为公司启用日期')
    date_end = fields.Date(u'结束日期', default=_default_date_end,
                           help=u'报表汇总的结束日期，默认为当前日期')
    c_category_id = fields.Many2one('core.category', u'客户类别',
                                    domain=[('type', '=', 'customer')],
                                    context={'type': 'customer'},
                                    help=u'按指定客户类别进行统计')
    partner_id = fields.Many2one('partner', u'客户',
                                 help=u'按指定客户进行统计')
    staff_id = fields.Many2one('staff', u'销售员',
                               help=u'按指定销售员进行统计')
    warehouse_id = fields.Many2one('warehouse', u'仓库',
                                   help=u'按指定仓库进行统计')

    @api.multi
    def button_ok(self):
        res = []
        if self.date_end < self.date_start:
            raise UserError(u'开始日期不能大于结束日期！')

        cond = [('date', '>=', self.date_start),
                ('date', '<=', self.date_end),
                ('state', '=', 'done')]
        if self.c_category_id:
            cond.append(
                ('partner_id.c_category_id', '=', self.c_category_id.id)
            )
        if self.partner_id:
            cond.append(('partner_id', '=', self.partner_id.id))
        if self.staff_id:
            cond.append(('staff_id', '=', self.staff_id.id))
        if self.warehouse_id:
            cond += ['|',('warehouse_id', '=', self.warehouse_id.id),
                     ('warehouse_dest_id', '=', self.warehouse_id.id)]
        delivery_obj = self.env['sell.delivery']
        count = sum_receipt_rate = 0
        for delivery in delivery_obj.search(cond, order='partner_id'):
            sell_amount = delivery.discount_amount + delivery.amount
            discount_amount = delivery.discount_amount
            amount = delivery.amount
            partner_cost = delivery.partner_cost
            # 用查找到的发货单信息来创建一览表
            receipt = balance = 0
            for order in self.env['money.order'].search(
                        [('state', '=', 'done')], order='name'):
                for source in order.source_ids:
                    if source.name.name == delivery.name:
                        receipt += source.this_reconcile

            # 如果是退货则金额均取反
            if not delivery.is_return:
                order_type = u'普通销售'
                warehouse = delivery.warehouse_id
            elif delivery.is_return:
                order_type = u'销售退回'
                sell_amount = - sell_amount
                discount_amount = - discount_amount
                amount = - amount
                partner_cost = - partner_cost
                warehouse = delivery.warehouse_dest_id
            # 计算回款率
            receipt_rate = (amount + partner_cost) != 0 and (receipt / (amount + partner_cost)) * 100 or 0
            line = self.env['sell.receipt'].create({
                'c_category_id': delivery.partner_id.c_category_id.id,
                'partner_id': delivery.partner_id.id,
                'staff_id': delivery.staff_id.id,
                'type': order_type,
                'date': delivery.date,
                'order_name': delivery.name,
                'warehouse_id': warehouse.id,
                'sell_amount': sell_amount,
                'discount_amount': discount_amount,
                'amount': amount,
                'partner_cost': partner_cost,
                'receipt': receipt,
                'balance': amount + partner_cost - receipt,
                'receipt_rate': receipt_rate,
                'note': delivery.note,
            })
            res.append(line.id)
            count += 1
            sum_receipt_rate += line.receipt_rate

        # 创建一览表的合计行
        if sum_receipt_rate == 0 and count == 0:
            receipt_rate = 100
        else:
            receipt_rate = sum_receipt_rate / count
        line_total = self.env['sell.receipt'].create({
            'order_name': u'平均回款率',
            'receipt_rate': receipt_rate,
        })
        res.append(line_total.id)
        return {
            'name': u'销售收款一览表',
            'view_mode': 'tree',
            'res_model': 'sell.receipt',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', res)],
            'limit': 65535,
        }
