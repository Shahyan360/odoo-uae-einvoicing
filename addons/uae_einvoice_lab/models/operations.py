import base64
import hashlib
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from decimal import Decimal,ROUND_HALF_UP
import requests
from lxml import etree
from odoo import api,fields,models
from odoo.exceptions import AccessError,UserError,ValidationError
from ..common import guard,decimal

GROUP='uae_einvoice_lab.group_manager'
NS={'cbc':'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac':'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
def element(parent,kind,name,text=None,**attrs):
    node=etree.SubElement(parent,'{'+NS[kind]+'}'+name,**{str(k):str(v) for k,v in attrs.items()})
    if text is not None: node.text=str(text)
    return node
def money(value): return str(decimal(value).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))

class Partner(models.Model):
    _inherit='res.partner'
    ue_trn=fields.Char(string='PINT-AE TRN')
    ue_endpoint=fields.Char(string='PINT-AE Endpoint')
    ue_endpoint_scheme=fields.Char(string='Endpoint Scheme')
    ue_legal_id=fields.Char(string='Legal Registration Identifier')
    ue_legal_scheme=fields.Char(string='Legal Identifier Scheme')

class Tax(models.Model):
    _inherit='account.tax'
    ue_category=fields.Selection([('S','Standard Rated'),('Z','Zero Rated'),('E','Exempt')],string='PINT-AE Category')
    ue_exemption_code=fields.Char()
    ue_exemption_reason=fields.Char()

class Uom(models.Model):
    _inherit='uom.uom'
    ue_code=fields.Char(string='UNECE Unit Code')

class Provider(models.Model):
    _name='ue.provider'
    _description='Provider-Agnostic ASP Laboratory Configuration'
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    mode=fields.Selection([('simulator','Local Simulator'),('sandbox','Explicitly Authorized Generic Sandbox')],default='simulator',required=True)
    sandbox_url=fields.Char()
    token_env=fields.Char(default='LAB_ASP_TOKEN')
    customization=fields.Char(default='urn:peppol:pint:billing-1@ae-1',required=True)
    profile=fields.Char(default='urn:peppol:bis:billing',required=True)
    transaction_code=fields.Char(string='Configured Invoice Transaction Flags',required=True)
    invoice_xsd=fields.Char(default='UBL-Invoice-2.1.xsd')
    credit_xsd=fields.Char(default='UBL-CreditNote-2.1.xsd')
    rule_files=fields.Text(help='One official compiled shared/AE XSLT file per line, relative to /opt/lab-schemas.')
    strict_validation=fields.Boolean(default=True)
    simulator_result=fields.Selection([('accepted','Simulated Acceptance'),('rejected','Simulated Rejection'),('timeout','Simulated Timeout')],default='accepted')
    max_attempts=fields.Integer(default=5)
    @api.constrains('sandbox_url','mode','max_attempts')
    def _valid(self):
        for p in self:
            url=urlparse(p.sandbox_url or '')
            if p.mode=='sandbox' and (url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment):
                raise ValidationError('The authorized generic sandbox requires an HTTPS base URL without embedded credentials.')
            if not 1<=p.max_attempts<=10: raise ValidationError('Retry limit must be 1 to 10.')
    def _schema_path(self,name):
        root=Path('/opt/lab-schemas').resolve()
        path=(root/(name or '')).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValidationError('Required official schema or compiled rules file is unavailable: '+str(name))
        return path

class Move(models.Model):
    _inherit='account.move'
    ue_provider_id=fields.Many2one('ue.provider',check_company=True)
    ue_document_ids=fields.One2many('ue.document','move_id',readonly=True)
    def action_ue_document(self):
        self.ensure_one();guard(self,GROUP)
        if self.state!='posted' or self.move_type not in ('out_invoice','out_refund') or not self.ue_provider_id:
            raise UserError('Select an ASP configuration on a posted customer invoice or credit note.')
        existing=self.ue_document_ids.sorted('revision',reverse=True)[:1]
        document=existing or self.env['ue.document'].create({'move_id':self.id,'provider_id':self.ue_provider_id.id})
        return {'type':'ir.actions.act_window','res_model':'ue.document','res_id':document.id,'view_mode':'form'}
    def button_draft(self):
        if self.ue_document_ids.filtered(lambda d:d.state in ('submitted','accepted','retry')):
            raise UserError('A transmitted document cannot be silently reset. Use the appropriate credit/correction process.')
        return super().button_draft()

class MoveLine(models.Model):
    _inherit='account.move.line'
    ue_document_allowance=fields.Boolean(string='Document-level Discount Line',default=False)

class Transmission(models.Model):
    _name='ue.transmission'
    _description='Immutable E-Invoice Transmission History'
    document_id=fields.Many2one('ue.document',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='document_id.company_id',store=True)
    occurred_at=fields.Datetime(default=fields.Datetime.now,required=True)
    actor_id=fields.Many2one('res.users',required=True)
    provider_state=fields.Char(required=True)
    payload_hash=fields.Char(required=True)
    note=fields.Text()
    @api.model_create_multi
    def create(self,vals_list):
        if not self.env.su: raise AccessError('History is created only by the transmission workflow.')
        return super().create(vals_list)
    def write(self,vals): raise AccessError('Transmission history is immutable.')
    def unlink(self): raise AccessError('Transmission history is immutable.')

class Document(models.Model):
    _name='ue.document'
    _description='Immutable Structured Invoice Snapshot'
    _inherit=['mail.thread']
    _check_company_auto=True
    move_id=fields.Many2one('account.move',required=True,check_company=True,ondelete='restrict')
    company_id=fields.Many2one(related='move_id.company_id',store=True)
    provider_id=fields.Many2one('ue.provider',required=True,check_company=True)
    revision=fields.Integer(default=1,required=True)
    uuid=fields.Char(default=lambda s:str(uuid.uuid4()),readonly=True,copy=False,required=True)
    xml_file=fields.Binary(readonly=True,attachment=True)
    filename=fields.Char(readonly=True)
    payload_hash=fields.Char(readonly=True)
    state=fields.Selection([(s,s.title()) for s in ('draft','validation_failed','ready','submitted','accepted','rejected','retry','exhausted')],default='draft',readonly=True,tracking=True)
    validation_level=fields.Selection([('none','Not Validated'),('demo','Demo Checks Only'),('schema','Official XSD and Rules Applied')],default='none',readonly=True)
    validation_messages=fields.Text(readonly=True)
    provider_state=fields.Char(readonly=True)
    submission_id=fields.Char(readonly=True)
    attempts=fields.Integer(readonly=True)
    next_retry=fields.Datetime(readonly=True)
    transmission_ids=fields.One2many('ue.transmission','document_id',readonly=True)
    _sql_constraints=[('revision_unique','unique(move_id,revision)','Document revision already exists.'),('uuid_unique','unique(uuid)','Document UUID already exists.')]
    @api.model_create_multi
    def create(self,vals_list):
        if not self.env.user.has_group(GROUP) or any(v.get('state','draft')!='draft' or v.get('xml_file') or v.get('payload_hash') for v in vals_list):
            raise AccessError('Create draft documents through the authorized workflow.')
        return super().create(vals_list)
    def write(self,vals):
        if {'state','validation_level','xml_file','payload_hash','provider_state','submission_id','attempts','next_retry','uuid','revision','move_id','provider_id','validation_messages'}.intersection(vals):
            raise AccessError('Use structured document workflow actions.')
        return super().write(vals)
    def _update(self,vals): return super(Document,self).write(vals)

    def _party(self,parent,name,partner):
        if not all((partner.name,partner.street,partner.city,partner.country_id.code,partner.state_id.name,
                    partner.ue_endpoint,partner.ue_endpoint_scheme)):
            raise ValidationError('Complete legal name/address/country/subdivision and endpoint/scheme for '+partner.name)
        if partner.ue_trn and not re.fullmatch(r'[0-9]{15}',partner.ue_trn):
            raise ValidationError('Configured TRN must contain 15 digits. This is structural, not registry validation.')
        party=element(element(parent,'cac',name),'cac','Party')
        element(party,'cbc','EndpointID',partner.ue_endpoint,schemeID=partner.ue_endpoint_scheme)
        address=element(party,'cac','PostalAddress')
        for tag,value in [('StreetName',partner.street),('AdditionalStreetName',partner.street2),('CityName',partner.city),('PostalZone',partner.zip),('CountrySubentity',partner.state_id.name)]:
            if value: element(address,'cbc',tag,value)
        element(element(address,'cac','Country'),'cbc','IdentificationCode',partner.country_id.code)
        if partner.ue_trn:
            tax=element(party,'cac','PartyTaxScheme');element(tax,'cbc','CompanyID',partner.ue_trn)
            element(element(tax,'cac','TaxScheme'),'cbc','ID','VAT')
        legal=element(party,'cac','PartyLegalEntity');element(legal,'cbc','RegistrationName',partner.name)
        if partner.ue_legal_id: element(legal,'cbc','CompanyID',partner.ue_legal_id,schemeID=partner.ue_legal_scheme or '')

    def _category(self,parent,tax):
        category=element(parent,'cac','TaxCategory')
        element(category,'cbc','ID',tax.ue_category)
        element(category,'cbc','Percent',money(tax.amount))
        if tax.ue_exemption_code: element(category,'cbc','TaxExemptionReasonCode',tax.ue_exemption_code)
        if tax.ue_exemption_reason: element(category,'cbc','TaxExemptionReason',tax.ue_exemption_reason)
        element(element(category,'cac','TaxScheme'),'cbc','ID','VAT')
        return category

    def _xml(self):
        self.ensure_one();move=self.move_id;provider=self.provider_id
        if move.state!='posted' or move.move_type not in ('out_invoice','out_refund'):
            raise ValidationError('Only posted customer invoices/credit notes may be mapped.')
        if move.company_id.country_id.code!='AE' or move.company_id.currency_id.name!='AED':
            raise ValidationError('This UAE mapping requires an AE company with AED company currency.')
        if not move.company_id.partner_id.ue_trn:
            raise ValidationError('Configure seller TRN for this scoped VAT-registered demonstration.')
        if not provider.transaction_code:
            raise ValidationError('Configure transaction flags from the current PINT-AE code list.')
        credit=move.move_type=='out_refund';kind='CreditNote' if credit else 'Invoice'
        root=etree.Element('{urn:oasis:names:specification:ubl:schema:xsd:'+kind+'-2}'+kind,
                           nsmap={None:'urn:oasis:names:specification:ubl:schema:xsd:'+kind+'-2',**NS})
        for tag,value in [('CustomizationID',provider.customization),('ProfileID',provider.profile),
                          ('ProfileExecutionID',provider.transaction_code),('ID',move.name),('UUID',self.uuid),('IssueDate',move.invoice_date)]:
            element(root,'cbc',tag,value)
        if not credit and move.invoice_date_due: element(root,'cbc','DueDate',move.invoice_date_due)
        element(root,'cbc','CreditNoteTypeCode' if credit else 'InvoiceTypeCode','381' if credit else '380')
        element(root,'cbc','DocumentCurrencyCode',move.currency_id.name)
        if move.currency_id.name!='AED': element(root,'cbc','TaxCurrencyCode','AED')
        if credit:
            original=move.reversed_entry_id
            if not original or original.state!='posted': raise ValidationError('Credit note must reference its posted original invoice.')
            ref=element(element(root,'cac','BillingReference'),'cac','InvoiceDocumentReference')
            element(ref,'cbc','ID',original.name);element(ref,'cbc','IssueDate',original.invoice_date)
        if move.currency_id.name!='AED':
            ref=element(root,'cac','AdditionalDocumentReference')
            element(ref,'cbc','ID','AED');element(ref,'cbc','DocumentTypeCode','aedtotal-incl-vat')
            element(ref,'cbc','DocumentDescription',money(abs(move.amount_total_signed)))
        self._party(root,'AccountingSupplierParty',move.company_id.partner_id)
        self._party(root,'AccountingCustomerParty',move.partner_id.commercial_partner_id)
        currency=move.currency_id.name
        lines=move.invoice_line_ids.filtered(lambda l:l.display_type=='product')
        if not lines: raise ValidationError('No invoice lines exist.')
        groups=defaultdict(lambda:{'net':Decimal('0'),'tax':Decimal('0'),'record':None})
        regular=[];allowances=[];line_total=Decimal('0');allowance_total=Decimal('0')
        for line in lines:
            taxes=line.tax_ids
            if len(taxes)!=1 or taxes.amount_type!='percent' or not taxes.ue_category:
                raise ValidationError('Each supported line requires one explicitly mapped percentage VAT tax.')
            tax=taxes
            if (tax.ue_category=='S' and tax.amount!=5) or (tax.ue_category in ('Z','E') and tax.amount!=0):
                raise ValidationError('This scoped mapper requires S=5%, Z/E=0%.')
            if tax.ue_category in ('Z','E') and not (tax.ue_exemption_code or tax.ue_exemption_reason):
                raise ValidationError('Configure the applicable zero/exempt reason from the specification.')
            net=decimal(line.price_subtotal);tax_amount=decimal(line.price_total)-net
            key=(tax.ue_category,tax.amount,tax.ue_exemption_code or '',tax.ue_exemption_reason or '')
            groups[key]['net']+=net;groups[key]['tax']+=tax_amount;groups[key]['record']=tax
            if line.ue_document_allowance:
                if net>=0: raise ValidationError('Document allowance must be a negative native invoice line.')
                allowances.append((line,tax,-net));allowance_total-=net
            else:
                if line.quantity<=0 or net<0: raise ValidationError('Use positive quantities and dedicated document-allowance lines.')
                regular.append((line,tax,net));line_total+=net
        for line,tax,amount in allowances:
            allowance=element(root,'cac','AllowanceCharge');element(allowance,'cbc','ChargeIndicator','false')
            element(allowance,'cbc','AllowanceChargeReason',line.name or 'Document discount')
            element(allowance,'cbc','Amount',money(amount),currencyID=currency)
            self._category(allowance,tax)
        total_tax=sum((g['tax'] for g in groups.values()),Decimal('0'))
        tax_total=element(root,'cac','TaxTotal');element(tax_total,'cbc','TaxAmount',money(total_tax),currencyID=currency)
        for group in groups.values():
            sub=element(tax_total,'cac','TaxSubtotal');element(sub,'cbc','TaxableAmount',money(group['net']),currencyID=currency)
            element(sub,'cbc','TaxAmount',money(group['tax']),currencyID=currency);self._category(sub,group['record'])
        if currency!='AED':
            total=element(root,'cac','TaxTotal');element(total,'cbc','TaxAmount',money(abs(move.amount_tax_signed)),currencyID='AED')
        net_total=line_total-allowance_total
        if abs(net_total-decimal(move.amount_untaxed))>Decimal('0.01') or abs(total_tax-decimal(move.amount_tax))>Decimal('0.01'):
            raise ValidationError('Mapped tax/net totals differ from native accounting. Review rounding and tax settings.')
        legal=element(root,'cac','LegalMonetaryTotal')
        for tag,value in [('LineExtensionAmount',line_total),('TaxExclusiveAmount',net_total),
                          ('TaxInclusiveAmount',net_total+total_tax),('AllowanceTotalAmount',allowance_total),
                          ('PayableAmount',net_total+total_tax)]:
            element(legal,'cbc',tag,money(value),currencyID=currency)
        for index,(line,tax,net) in enumerate(regular,1):
            invoice_line=element(root,'cac','CreditNoteLine' if credit else 'InvoiceLine')
            element(invoice_line,'cbc','ID',index)
            code=line.product_uom_id.ue_code
            if not code: raise ValidationError('Configure the UNECE unit code for '+line.product_uom_id.name)
            element(invoice_line,'cbc','CreditedQuantity' if credit else 'InvoicedQuantity',str(decimal(line.quantity)),unitCode=code)
            element(invoice_line,'cbc','LineExtensionAmount',money(net),currencyID=currency)
            before=line.tax_ids.compute_all(line.price_unit,currency=move.currency_id,quantity=line.quantity,product=line.product_id,partner=move.partner_id)['total_excluded']
            discount=decimal(before)-net
            if discount>Decimal('0.005'):
                allowance=element(invoice_line,'cac','AllowanceCharge');element(allowance,'cbc','ChargeIndicator','false')
                element(allowance,'cbc','AllowanceChargeReason','Line discount');element(allowance,'cbc','Amount',money(discount),currencyID=currency)
            item=element(invoice_line,'cac','Item');element(item,'cbc','Name',line.name or line.product_id.name)
            category=self._category(item,tax);category.tag='{'+NS['cac']+'}ClassifiedTaxCategory'
            price=element(invoice_line,'cac','Price');element(price,'cbc','PriceAmount',str(decimal(before)/decimal(line.quantity)),currencyID=currency)
        return etree.tostring(root,xml_declaration=True,encoding='UTF-8',pretty_print=True)

    def action_validate(self):
        guard(self,GROUP)
        for doc in self:
            if doc.state not in ('draft','validation_failed'):
                raise UserError('Only draft or failed-validation snapshots may be rebuilt.')
            try:
                raw=doc._xml();provider=doc.provider_id
                level='demo'
                if provider.strict_validation or provider.mode=='sandbox':
                    xsd=provider._schema_path(provider.credit_xsd if doc.move_id.move_type=='out_refund' else provider.invoice_xsd)
                    parser=etree.XMLParser(resolve_entities=False,no_network=True)
                    schema=etree.XMLSchema(etree.parse(str(xsd),parser))
                    schema.assertValid(etree.fromstring(raw,parser))
                    names=[name.strip() for name in (provider.rule_files or '').splitlines() if name.strip()]
                    if len(names)<2: raise ValidationError('Configure both shared PINT and AE-specific compiled rules.')
                    try: from saxonche import PySaxonProcessor
                    except ImportError: raise ValidationError('Install the documented SaxonC HE dependency for official rule evaluation.')
                    with PySaxonProcessor(license=False) as processor:
                        xslt=processor.new_xslt30_processor()
                        for name in names:
                            executable=xslt.compile_stylesheet(stylesheet_file=str(provider._schema_path(name)))
                            svrl=executable.transform_to_string(xdm_node=processor.parse_xml(xml_text=raw.decode()))
                            results=etree.fromstring(svrl.encode(),parser)
                            failed=results.xpath('//*[local-name()="failed-assert" and not(@flag="warning")]')
                            if failed: raise ValidationError('; '.join(' '.join(x.itertext()).strip() for x in failed)[:3000])
                    level='schema'
                doc._update({'xml_file':base64.b64encode(raw),'filename':doc.uuid+'.xml',
                    'payload_hash':hashlib.sha256(raw).hexdigest(),'state':'ready','validation_level':level,
                    'validation_messages':'Official schema and configured rules applied.' if level=='schema' else 'Demo mapping checks only. Not schema-validated or certified.'})
            except (ValidationError,etree.Error) as error:
                doc._update({'state':'validation_failed','validation_level':'none','validation_messages':str(error)[:4000]})
        return True

    def _history(self,state,note=''):
        self.ensure_one()
        self.env['ue.transmission'].sudo().create({'document_id':self.id,'actor_id':self.env.uid,
            'provider_state':state,'payload_hash':self.payload_hash,'note':note})
        self.message_post(body='Transmission state: '+state)

    def action_submit(self):
        guard(self,GROUP)
        for doc in self:
            if doc.state not in ('ready','retry'): continue
            if doc.next_retry and doc.next_retry>fields.Datetime.now(): continue
            provider=doc.provider_id
            if provider.mode=='sandbox' and doc.validation_level!='schema': raise UserError('Official XSD and shared/AE rules are required before sandbox transmission.')
            if doc.attempts>=provider.max_attempts:
                doc._update({'state':'exhausted'});continue
            doc._update({'attempts':doc.attempts+1})
            try:
                if provider.mode=='simulator':
                    if provider.simulator_result=='timeout': raise requests.Timeout()
                    result={'id':'SIM-'+doc.uuid,'status':'SIMULATED_'+provider.simulator_result.upper()}
                    state=provider.simulator_result
                else:
                    token=os.environ.get(provider.token_env or '')
                    if not token: raise UserError('Authorized sandbox token is unavailable.')
                    response=requests.post(provider.sandbox_url.rstrip('/')+'/submissions',data=base64.b64decode(doc.xml_file),
                        headers={'Authorization':'Bearer '+token,'Content-Type':'application/xml','Idempotency-Key':doc.uuid+':'+doc.payload_hash},timeout=(5,30))
                    if response.status_code==429 or response.status_code>=500: raise requests.Timeout()
                    if response.status_code not in (200,201,202): raise UserError('Sandbox rejected the submission; review provider configuration.')
                    result=response.json();state={'ACCEPTED':'accepted','REJECTED':'rejected','SUBMITTED':'submitted'}.get(result.get('status'))
                    if not state or not result.get('id'): raise UserError('Unexpected sandbox response; acceptance was not inferred.')
                doc._update({'state':state,'provider_state':result['status'],'submission_id':str(result['id']),'next_retry':False})
                doc._history(result['status'],'Simulator outcome' if provider.mode=='simulator' else 'Authorized generic sandbox response')
            except (requests.RequestException,ValueError):
                doc._update({'state':'exhausted' if doc.attempts>=provider.max_attempts else 'retry',
                    'provider_state':'TIMEOUT_OR_TRANSPORT_ERROR','next_retry':fields.Datetime.now()+timedelta(minutes=2**doc.attempts)})
                doc._history('TIMEOUT_OR_TRANSPORT_ERROR','Retry preserves the same snapshot and idempotency key.')
        return True

    def action_poll(self):
        guard(self,GROUP)
        for doc in self:
            provider=doc.provider_id
            if doc.state!='submitted' or provider.mode!='sandbox': continue
            token=os.environ.get(provider.token_env or '')
            if not token: raise UserError('Sandbox token is unavailable.')
            from urllib.parse import quote
            response=requests.get(provider.sandbox_url.rstrip('/')+'/submissions/'+quote(doc.submission_id,safe=''),headers={'Authorization':'Bearer '+token},timeout=(5,30))
            if response.status_code!=200: raise UserError('Sandbox status request failed.')
            result=response.json();state={'ACCEPTED':'accepted','REJECTED':'rejected','SUBMITTED':'submitted'}.get(result.get('status'))
            if not state: raise UserError('Unrecognized provider state; no acceptance was recorded.')
            doc._update({'state':state,'provider_state':result['status']});doc._history(result['status'])
        return True

    def action_new_revision(self):
        guard(self,GROUP);self.ensure_one()
        if self.state not in ('rejected','validation_failed'): raise UserError('Only rejected/invalid documents can be revised; accepted invoices require the legal correction process.')
        self.env.cr.execute('SELECT id FROM account_move WHERE id=%s FOR UPDATE',(self.move_id.id,))
        latest=self.search([('move_id','=',self.move_id.id)],order='revision desc',limit=1)
        new=self.create({'move_id':self.move_id.id,'provider_id':self.provider_id.id,'revision':latest.revision+1})
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':new.id,'view_mode':'form'}
    @api.model
    def _cron_retry(self):
        self.search([('state','=','retry'),('next_retry','<=',fields.Datetime.now())],limit=50).action_submit()
