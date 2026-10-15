import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, DealItem, ShopeeCategory, CleanupDealsResult } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';

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
    NzToolTipModule,
    NzModalModule,
    NzCheckboxModule
  ],
  templateUrl: './deals.component.html',
  styleUrls: ['./deals.component.css']
})
export class DealsComponent implements OnInit {
  deals: DealItem[] = [];
  loading = false;
  crawlLoading = false;
  cleanupLoading = false;

  // Modal kết quả dọn dẹp deal
  cleanupResultModalVisible = false;
  lastCleanupResult: CleanupDealsResult | null = null;

  selectedNiche: string = '';
  selectedStatus: string = '';
  searchQuery: string = '';
  onlyVip: boolean = false;

  // Ngành được chọn để cào deal
  crawlNiche: string = '';

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
    { label: 'Đã đăng (Posted)', value: 'posted' },
    { label: 'Hết hạn (Expired)', value: 'expired' }
  ];

  // Modal 28 ngành hàng Shopee
  categoriesModalVisible = false;
  categoriesLoading = false;
  shopeeCategories: ShopeeCategory[] = [];
  selectedCategories: { [name: string]: boolean } = {};
  syncingCategories = false;

  constructor(
    private api: ApiService,
    private msg: NzMessageService,
    private modal: NzModalService
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
    this.api.getDeals(this.selectedNiche, this.selectedStatus, this.searchQuery, this.onlyVip ? true : undefined).subscribe({
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

  toggleOnlyVip(): void {
    this.onlyVip = !this.onlyVip;
    this.fetchDeals();
  }

  triggerCrawl(specificNiche?: string): void {
    const target = specificNiche !== undefined ? specificNiche : this.crawlNiche;
    this.crawlLoading = true;
    this.api.crawlDeals(target).subscribe({
      next: (res) => {
        this.crawlLoading = false;
        this.msg.success(res.message || 'Cào deal thành công!');
        this.fetchDeals();
      },
      error: (err) => {
        this.crawlLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi kích hoạt cào deal!');
      }
    });
  }

  // --- QUÉT & DỌN DẸP DEAL HẾT SALE ---
  triggerCleanup(): void {
    this.modal.confirm({
      nzTitle: '🧹 Quét & Tự Động Xóa Deal Hết Sale',
      nzContent: 'Hệ thống sẽ đối chiếu dữ liệu với Live Flash Sale Shopee và kiểm tra link từng sản phẩm. Các deal đã hết thời gian sale, bị xóa khỏi sàn hoặc báo hết hàng sẽ được tự động xóa khỏi cơ sở dữ liệu và dọn dẹp cache ảnh. Bạn có muốn tiếp tục?',
      nzOkText: 'Quét & Dọn Dẹp Ngay',
      nzOkDanger: true,
      nzCancelText: 'Hủy bỏ',
      nzOnOk: () => this.executeCleanup()
    });
  }

  executeCleanup(): void {
    this.cleanupLoading = true;
    this.api.cleanupExpiredDeals(true).subscribe({
      next: (res) => {
        this.cleanupLoading = false;
        this.lastCleanupResult = res;
        if (res.removed_count > 0) {
          this.cleanupResultModalVisible = true;
          this.msg.success(`Đã tự động loại bỏ & xóa ${res.removed_count} deal hết hạn sale!`);
        } else {
          this.msg.info(res.message || 'Tất cả deal hiện tại đều còn sale hợp lệ!');
        }
        this.fetchDeals();
      },
      error: (err) => {
        this.cleanupLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi quét dọn deal hết sale!');
      }
    });
  }

  closeCleanupResultModal(): void {
    this.cleanupResultModalVisible = false;
  }

  // --- MODAL SHOPEE CATEGORIES ---
  openCategoriesModal(): void {
    this.categoriesModalVisible = true;
    this.categoriesLoading = true;
    this.selectedCategories = {};
    if (this.crawlNiche) {
      this.selectedCategories[this.crawlNiche] = true;
    }
    this.api.getShopeeCategories().subscribe({
      next: (res) => {
        this.shopeeCategories = res.categories || [];
        this.categoriesLoading = false;
      },
      error: () => {
        this.categoriesLoading = false;
        this.msg.error('Không thể tải danh mục Shopee!');
      }
    });
  }

  closeCategoriesModal(): void {
    this.categoriesModalVisible = false;
  }

  toggleCategory(name: string): void {
    this.selectedCategories[name] = !this.selectedCategories[name];
  }

  selectAllCategories(): void {
    for (const c of this.shopeeCategories) {
      this.selectedCategories[c.name] = true;
    }
  }

  deselectAllCategories(): void {
    this.selectedCategories = {};
  }

  crawlSelectedFromModal(catName: string): void {
    this.crawlNiche = catName.toLowerCase();
    this.closeCategoriesModal();
    this.triggerCrawl(this.crawlNiche);
  }

  syncCategoriesToNiches(): void {
    const chosen = Object.keys(this.selectedCategories).filter(k => this.selectedCategories[k]);
    if (chosen.length === 0) {
      this.msg.warning('Vui lòng chọn ít nhất 1 ngành hàng Shopee!');
      return;
    }
    this.syncingCategories = true;
    this.api.syncShopeeNiches(chosen).subscribe({
      next: (res) => {
        this.syncingCategories = false;
        this.msg.success(res.message || 'Đã đồng bộ ngành hàng vào cấu hình bot!');
        this.loadNiches();
        this.closeCategoriesModal();
      },
      error: () => {
        this.syncingCategories = false;
        this.msg.error('Lỗi khi đồng bộ ngành hàng!');
      }
    });
  }

  getScoreColor(score: number): string {
    if (score >= 80) return '#10b981';
    if (score >= 65) return '#f59e0b';
    return '#ef4444';
  }
}
