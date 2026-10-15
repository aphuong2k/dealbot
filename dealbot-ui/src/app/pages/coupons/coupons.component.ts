import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, CouponItem, EventItem, SaleCampaign } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';

@Component({
  selector: 'app-coupons',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzInputModule,
    NzSelectModule,
    NzSpinModule,
    NzModalModule,
    NzTabsModule,
    NzTagModule,
    NzToolTipModule
  ],
  templateUrl: './coupons.component.html',
  styleUrls: ['./coupons.component.css']
})
export class CouponsComponent implements OnInit {
  coupons: CouponItem[] = [];
  campaigns: SaleCampaign[] = [];
  events: EventItem[] = [];

  loading = false;
  refreshLoading = false;
  broadcastLoading = false;
  planDigestLoading = false;

  selectedCategory: string = '';
  searchQuery: string = '';

  categoryOptions = [
    { label: '🌐 Tất Cả Loại Mã', value: '' },
    { label: '🎟 Toàn Sàn & Siêu Voucher', value: 'toan_san' },
    { label: '🚚 Freeship 0đ & Freeship Xtra', value: 'freeship' },
    { label: '🎬 Shopee Live & Video (-50%)', value: 'live_video' },
    { label: '⚡ Khung Giờ Flash Sale (1K - 9K)', value: 'flash_sale' },
    { label: '💳 Ví ShopeePay & Nạp Thẻ', value: 'shopeepay' },
    { label: '🛍 Theo Ngành Hàng Chính Hãng', value: 'nganh_hang' }
  ];

  addEventModalVisible = false;
  newEvent: EventItem = {
    title: '',
    merchant: 'shopee',
    start: '2026-10-16T00:00:00',
    end: '2026-10-18T23:59:00',
    detail: '',
    link: ''
  };

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.loading = true;
    this.api.getCoupons(this.selectedCategory).subscribe({
      next: (c) => this.coupons = c,
      error: () => {}
    });

    this.api.getDailyCampaigns().subscribe({
      next: (camps) => this.campaigns = camps,
      error: () => {}
    });

    this.api.getEvents().subscribe({
      next: (e) => {
        this.events = e;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  filterCoupons(): void {
    this.loading = true;
    this.api.getCoupons(this.selectedCategory).subscribe({
      next: (c) => {
        if (this.searchQuery && this.searchQuery.trim()) {
          const q = this.searchQuery.toLowerCase();
          this.coupons = c.filter(item => 
            (item.title && item.title.toLowerCase().includes(q)) ||
            (item.code && item.code.toLowerCase().includes(q)) ||
            (item.detail && item.detail.toLowerCase().includes(q))
          );
        } else {
          this.coupons = c;
        }
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  triggerRefresh(): void {
    this.refreshLoading = true;
    this.api.refreshCoupons().subscribe({
      next: (res) => {
        this.refreshLoading = false;
        this.msg.success(res.message || 'Đã tổng hợp mã Shopee VIP và link lưu mã mới nhất!');
        this.fetchData();
      },
      error: (err) => {
        this.refreshLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi quét tổng hợp mã giảm giá!');
      }
    });
  }

  planDigestToGroups(): void {
    this.planDigestLoading = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.planDigestLoading = false;
        this.msg.success(res.message || 'Đã lên lịch phân bổ bản tin săn sale hôm nay vào các group!');
      },
      error: () => {
        this.planDigestLoading = false;
        this.msg.error('Lỗi khi lập lịch bản tin săn sale!');
      }
    });
  }

  broadcastTelegram(): void {
    this.broadcastLoading = true;
    this.api.postDigestTelegram().subscribe({
      next: (res) => {
        this.broadcastLoading = false;
        this.msg.success(res.message || 'Đã phát sóng bản tin mã giảm giá lên kênh Telegram!');
      },
      error: () => {
        this.broadcastLoading = false;
        this.msg.error('Lỗi khi phát sóng bản tin Telegram!');
      }
    });
  }

  copyLink(url: string, label: string = 'Link Affiliate'): void {
    if (!url) return;
    navigator.clipboard.writeText(url).then(() => {
      this.msg.success(`Đã copy ${label} vào bộ nhớ tạm!`);
    }).catch(() => {
      this.msg.info(`Link: ${url}`);
    });
  }

  getCategoryBadge(category?: string): { text: string; color: string } {
    switch (category) {
      case 'toan_san': return { text: 'Toàn Sàn', color: 'volcano' };
      case 'freeship': return { text: 'Freeship', color: 'green' };
      case 'live_video': return { text: 'Live & Video', color: 'magenta' };
      case 'flash_sale': return { text: 'Flash Sale', color: 'orange' };
      case 'shopeepay': return { text: 'ShopeePay', color: 'blue' };
      case 'nganh_hang': return { text: 'Ngành Hàng', color: 'purple' };
      default: return { text: 'Khuyến Mãi', color: 'default' };
    }
  }

  openAddEvent(): void {
    const now = new Date();
    this.newEvent = {
      title: '',
      merchant: 'shopee',
      start: now.toISOString().slice(0, 19),
      end: new Date(now.getTime() + 86400000 * 3).toISOString().slice(0, 19),
      detail: '',
      link: ''
    };
    this.addEventModalVisible = true;
  }

  saveNewEvent(): void {
    if (!this.newEvent.title || !this.newEvent.link) {
      this.msg.warning('Vui lòng điền tiêu đề và link affiliate!');
      return;
    }
    const updated = [...this.events, this.newEvent];
    this.api.saveEvents(updated).subscribe({
      next: () => {
        this.msg.success('Đã thêm sự kiện vào events.yaml!');
        this.addEventModalVisible = false;
        this.fetchData();
      },
      error: () => this.msg.error('Lỗi khi lưu sự kiện!')
    });
  }

  deleteEvent(idx: number): void {
    const updated = this.events.filter((_, i) => i !== idx);
    this.api.saveEvents(updated).subscribe({
      next: () => {
        this.msg.success('Đã xóa sự kiện!');
        this.fetchData();
      },
      error: () => this.msg.error('Lỗi khi xóa sự kiện!')
    });
  }
}
