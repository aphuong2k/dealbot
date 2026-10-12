import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, DealItem } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';

@Component({
  selector: 'app-deals',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzInputModule,
    NzSelectModule,
    NzTagModule,
    NzSpinModule,
    NzBadgeModule,
    NzToolTipModule
  ],
  templateUrl: './deals.component.html',
  styleUrls: ['./deals.component.css']
})
export class DealsComponent implements OnInit {
  deals: DealItem[] = [];
  loading = false;
  crawlLoading = false;

  selectedNiche: string = '';
  selectedStatus: string = '';
  searchQuery: string = '';

  niches = [
    { label: 'Tất cả ngách', value: '' },
    { label: 'Gia dụng', value: 'gia dụng' },
    { label: 'Mẹ và bé', value: 'mẹ và bé' },
    { label: 'Mỹ phẩm', value: 'mỹ phẩm' },
    { label: 'Đồ công nghệ giá rẻ', value: 'đồ công nghệ giá rẻ' }
  ];

  statuses = [
    { label: 'Tất cả trạng thái', value: '' },
    { label: 'Mới cào (New)', value: 'new' },
    { label: 'Đã lên lịch (Planned)', value: 'planned' },
    { label: 'Hết hạn (Expired)', value: 'expired' }
  ];

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchDeals();
    this.loadNiches();
  }

  loadNiches(): void {
    this.api.getConfig().subscribe({
      next: (cfg) => {
        if (cfg && cfg.niches) {
          const dynamicNiches = cfg.niches.map((n: string) => ({
            label: n.charAt(0).toUpperCase() + n.slice(1),
            value: n
          }));
          this.niches = [{ label: 'Tất cả ngách', value: '' }, ...dynamicNiches];
        }
      },
      error: () => {}
    });
  }

  fetchDeals(): void {
    this.loading = true;
    this.api.getDeals(this.selectedNiche, this.selectedStatus, this.searchQuery).subscribe({
      next: (data) => {
        this.deals = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải danh sách deal!');
      }
    });
  }

  triggerCrawl(): void {
    this.crawlLoading = true;
    this.api.crawlDeals().subscribe({
      next: (res) => {
        this.crawlLoading = false;
        this.msg.success(res.message);
        setTimeout(() => this.fetchDeals(), 3000);
      },
      error: () => {
        this.crawlLoading = false;
        this.msg.error('Lỗi khi kích hoạt cào deal!');
      }
    });
  }

  getScoreColor(score: number): string {
    if (score >= 80) return '#10b981';
    if (score >= 65) return '#f59e0b';
    return '#ef4444';
  }
}
