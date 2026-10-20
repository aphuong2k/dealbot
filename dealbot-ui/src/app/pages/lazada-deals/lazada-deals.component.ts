import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ApiService,
  LazadaCookieInfo,
  LazadaHunterConfig,
  LazadaTrackedProduct,
  LazadaFoundDeal,
  LazadaHunterLog,
  GroupItem,
  LazadaHunterStatus,
  LazadaGeneralStatus,
  DeepDropDeal,
  RadarCategoryItem,
  RadarCategoriesResponse,
  TmallCategoryItem,
  TmallShopItem,
  LazadaTmallStatus
} from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzSwitchModule } from 'ng-zorro-antd/switch';

@Component({
  selector: 'app-lazada-deals',
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
    NzToolTipModule,
    NzSwitchModule
  ],
  templateUrl: './lazada-deals.component.html',
  styleUrls: ['./lazada-deals.component.css']
})
export class LazadaDealsComponent implements OnInit {
  loading = false;
  activeTabIndex = 0;

  // Cookie
  cookieInfo: LazadaCookieInfo = {
    exists: false,
    count: 0,
    user_name: null,
    updated_at: null,
    size_bytes: 0,
    is_valid: false,
    raw_preview: ''
  };
  cookieInput = '';
  savingCookie = false;
  testingCookie = false;

  // Config
  config: LazadaHunterConfig = {
    enabled: true,
    interval_minutes: 5,
    filter_mall_only: true,
    min_discount_pct: 10,
    selected_groups: [],
    max_search_results: 10
  };
  savingConfig = false;

  // Tracked Products
  products: LazadaTrackedProduct[] = [];
  productSearch = '';
  newProductModalVisible = false;
  editingProduct: Partial<LazadaTrackedProduct> = {
    name: '',
    clean_keyword: '',
    avg_price: 100000,
    filter_mall_only: 1,
    min_discount_pct: 10
  };
  isEditing = false;

  // Found Deals (Theo dõi model)
  deals: LazadaFoundDeal[] = [];
  dealsLoading = false;
  // Hunter Runner
  runningHunterNow = false;

  hunterStatus: LazadaHunterStatus = {
    is_running: false,
    trigger_type: 'none',
    started_at: 0,
    elapsed_seconds: 0,
    total_products: 0,
    current_index: 0,
    current_product_name: '',
    deals_found: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  get hunterProgressPct(): number {
    if (!this.hunterStatus.total_products || this.hunterStatus.total_products <= 0) return 0;
    return Math.min(100, Math.round((this.hunterStatus.current_index / this.hunterStatus.total_products) * 100));
  }

  // Deep Drops (Radar Sập Sàn Toàn Sàn)
  deepDrops: DeepDropDeal[] = [];
  deepDropsLoading = false;
  selectedCategory = 'all';
  runningGeneralScanNow = false;

  generalStatus: LazadaGeneralStatus = {
    is_running: false,
    started_at: 0,
    elapsed_seconds: 0,
    current_category: '',
    current_keyword: '',
    total_keywords: 0,
    current_index: 0,
    items_scanned: 0,
    deals_found: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  get generalProgressPct(): number {
    if (!this.generalStatus.total_keywords || this.generalStatus.total_keywords <= 0) return 0;
    return Math.min(100, Math.round((this.generalStatus.current_index / this.generalStatus.total_keywords) * 100));
  }

  // --- TMALL BRAND DIRECTORY & SHOP SCANNER (6 NHÓM TRỌNG ĐIỂM) ---
  tmallCategories: TmallCategoryItem[] = [];
  tmallCategoriesLoading = false;
  selectedTmallCategoryId = '2'; // Mặc định nhóm "Điện Gia Dụng"
  tmallShops: TmallShopItem[] = [];
  tmallShopsLoading = false;
  tmallShopSearch = '';
  runningTmallScanNow = false;
  syncingTmallBrands = false;
  tmallMinDropPct = 80; // Ngưỡng lọc sập sàn chuẩn 80% - 85% (loại bỏ giá ảo)

  tmallStatus: LazadaTmallStatus = {
    is_running: false,
    trigger_type: 'none',
    started_at: 0,
    elapsed_seconds: 0,
    current_category_name: '',
    current_shop_name: '',
    current_shop_index: 0,
    total_shops: 0,
    items_scanned: 0,
    deals_found: 0,
    message: '',
    last_finished_at: 0,
    last_result: null
  };

  get tmallProgressPct(): number {
    if (!this.tmallStatus.total_shops || this.tmallStatus.total_shops <= 0) return 0;
    return Math.min(100, Math.round((this.tmallStatus.current_shop_index / this.tmallStatus.total_shops) * 100));
  }

  get filteredTmallShops(): TmallShopItem[] {
    if (!this.tmallShopSearch.trim()) return this.tmallShops;
    const q = this.tmallShopSearch.toLowerCase();
    return this.tmallShops.filter(s => s.shop_name.toLowerCase().includes(q) || s.shop_slug.toLowerCase().includes(q));
  }

  get selectedTmallCategory(): TmallCategoryItem | undefined {
    return this.tmallCategories.find(c => c.id === this.selectedTmallCategoryId);
  }

  targetCategoryNames = [
    'Điện Gia Dụng',
    'Điện Tử & Phụ Kiện',
    'Bách Hóa',
    'Đời Sống',
    'Thời Trang Thể Thao',
    'Thời Trang Nam'
  ];

  isPriorityCategory(catName: string): boolean {
    return this.targetCategoryNames.some(t => t.toLowerCase() === (catName || '').toLowerCase());
  }

  get priorityCategories(): TmallCategoryItem[] {
    return this.tmallCategories.filter(c => this.isPriorityCategory(c.name));
  }

  get otherCategories(): TmallCategoryItem[] {
    return this.tmallCategories.filter(c => !this.isPriorityCategory(c.name));
  }

  // FB Groups selection
  availableGroups: GroupItem[] = [];
  selectedGroupUrls: string[] = [];
  selectedAccount = 'nick_a';
  scanningFb = false;
  scanFbStatus: any = null;

  // Test search Lazada
  testKeyword = '';
  testFilterMall = true;
  testSearching = false;
  testSearchResults: any[] = [];
  testSearchModalVisible = false;

  // Hunter Logs
  hunterLogs: LazadaHunterLog[] = [];
  loadingLogs = false;
  clearingLogs = false;

  constructor(
    private api: ApiService,
    private msg: NzMessageService,
    private modal: NzModalService
  ) {}

  ngOnInit(): void {
    this.loadAll();
    this.pollScanStatus();

    this.api.tasksStatus$.subscribe(st => {
      const wasHunterRunning = this.hunterStatus.is_running;
      this.hunterStatus = st.lazada_hunter;
      this.runningHunterNow = this.hunterStatus.is_running;
      if (wasHunterRunning && !this.hunterStatus.is_running) {
        this.loadHunterLogs();
        this.loadDeals();
      }

      if (st.lazada_general) {
        const wasGeneralRunning = this.generalStatus.is_running;
        this.generalStatus = st.lazada_general;
        this.runningGeneralScanNow = this.generalStatus.is_running;
        if (wasGeneralRunning && !this.generalStatus.is_running) {
          this.loadDeepDrops();
        }
      }

      if (st.lazada_tmall) {
        const wasTmallRunning = this.tmallStatus.is_running;
        this.tmallStatus = st.lazada_tmall;
        this.runningTmallScanNow = this.tmallStatus.is_running;
        if (wasTmallRunning && !this.tmallStatus.is_running) {
          this.loadDeepDrops();
          this.loadTmallCategories();
        }
      }
    });
  }

  loadAll(): void {
    this.loadCookie();
    this.loadConfig();
    this.loadGeneralConfig();
    this.loadProducts();
    this.loadDeals();
    this.loadDeepDrops();
    this.loadGroups();
    this.loadHunterLogs();
    this.loadDeepDropLogs();
    this.loadRadarCategories();
    this.loadTmallCategories();
  }

  loadCookie(): void {
    this.api.getLazadaCookie().subscribe({
      next: (res) => (this.cookieInfo = res),
      error: () => {}
    });
  }

  loadConfig(): void {
    this.api.getLazadaHunterConfig().subscribe({
      next: (res) => {
        this.config = res;
        this.selectedGroupUrls = res.selected_groups || [];
      },
      error: () => {}
    });
  }

  loadProducts(): void {
    this.loading = true;
    this.api.getLazadaTrackedProducts().subscribe({
      next: (res) => {
        this.products = res;
        this.loading = false;
      },
      error: () => (this.loading = false)
    });
  }

  loadDeals(): void {
    this.dealsLoading = true;
    this.api.getLazadaDeals(60).subscribe({
      next: (res) => {
        this.deals = res;
        this.dealsLoading = false;
      },
      error: () => (this.dealsLoading = false)
    });
  }

  loadDeepDrops(): void {
    this.deepDropsLoading = true;
    const cat = this.selectedCategory === 'all' ? undefined : this.selectedCategory;
    this.api.getDeepDrops(cat, 60).subscribe({
      next: (res) => {
        this.deepDrops = res;
        this.deepDropsLoading = false;
      },
      error: () => (this.deepDropsLoading = false)
    });
  }

  filterCategory(cat: string): void {
    this.selectedCategory = cat;
    this.loadDeepDrops();
  }

  runGeneralScanNow(): void {
    if (this.generalStatus.is_running) {
      this.msg.warning('Radar quét sập sàn đang chạy, vui lòng chờ trong giây lát!');
      return;
    }
    this.runningGeneralScanNow = true;
    this.api.triggerDeepDropsScan().subscribe({
      next: (res) => {
        this.msg.success(res.message || 'Đã kích hoạt Radar quét sập sàn Tmall trong nền!');
      },
      error: (err) => {
        this.runningGeneralScanNow = false;
        this.msg.error(err?.error?.detail || err?.error?.message || 'Lỗi khi kích hoạt Radar quét.');
      }
    });
  }

  deleteDeal(id: number): void {
    if (confirm(`Bạn có chắc muốn xóa deal #${id}?`)) {
      this.api.deleteLazadaDeal(id).subscribe({
        next: () => {
          this.msg.success(`Đã xóa deal #${id}.`);
          this.loadDeals();
        },
        error: () => this.msg.error('Lỗi khi xóa deal.')
      });
    }
  }

  clearAllDeals(): void {
    this.modal.confirm({
      nzTitle: 'Xác nhận xóa toàn bộ deal Lazada đã săn được?',
      nzContent: 'Toàn bộ danh sách deal Lazada đã phát hiện sẽ được làm sạch.',
      nzOkText: 'Xóa sạch',
      nzOkDanger: true,
      nzOnOk: () => {
        this.api.clearLazadaDeals().subscribe({
          next: () => {
            this.msg.success('Đã xóa toàn bộ deal đã săn.');
            this.loadDeals();
          },
          error: () => this.msg.error('Lỗi khi xóa danh sách deal.')
        });
      }
    });
  }

  deleteSingleDeepDrop(id: number): void {
    if (confirm(`Xác nhận xóa kèo sập sàn #${id}?`)) {
      this.api.deleteDeepDrop(id).subscribe({
        next: () => {
          this.msg.success(`Đã xóa kèo sập sàn #${id}.`);
          this.loadDeepDrops();
        },
        error: () => this.msg.error('Lỗi khi xóa kèo.')
      });
    }
  }

  clearDeepDropsList(): void {
    this.modal.confirm({
      nzTitle: 'Xác nhận xóa toàn bộ danh sách kèo sập sàn?',
      nzContent: 'Toàn bộ dữ liệu kèo sập sàn Tmall đã quét sẽ được dọn dẹp sạch.',
      nzOkText: 'Xóa sạch ngay',
      nzOkDanger: true,
      nzOnOk: () => {
        this.api.clearDeepDrops().subscribe({
          next: () => {
            this.msg.success('Đã xóa danh sách kèo sập sàn thành công.');
            this.loadDeepDrops();
          },
          error: () => this.msg.error('Lỗi khi xóa danh sách kèo.')
        });
      }
    });
  }

  newHunterGroupUrl = '';
  newHunterGroupName = '';
  addingHunterGroup = false;

  loadGroups(): void {
    this.api.getLazadaHunterGroups().subscribe({
      next: (res) => {
        this.availableGroups = res;
      },
      error: () => {}
    });
  }

  addHunterGroup(): void {
    if (!this.newHunterGroupUrl.trim()) {
      this.msg.warning('Vui lòng nhập đường dẫn nhóm Facebook.');
      return;
    }
    this.addingHunterGroup = true;
    this.api.addLazadaHunterGroup(this.newHunterGroupUrl, this.newHunterGroupName).subscribe({
      next: (res) => {
        this.addingHunterGroup = false;
        this.msg.success(res.message || 'Đã thêm nhóm quét Lazada thành công!');
        this.newHunterGroupUrl = '';
        this.newHunterGroupName = '';
        this.loadGroups();
      },
      error: (err) => {
        this.addingHunterGroup = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi thêm nhóm.');
      }
    });
  }

  removeHunterGroup(url: string, event?: Event): void {
    if (event) event.stopPropagation();
    this.api.removeLazadaHunterGroup(url).subscribe({
      next: () => {
        this.msg.success('Đã gỡ nhóm khỏi danh sách quét Lazada.');
        this.selectedGroupUrls = this.selectedGroupUrls.filter(u => u !== url);
        this.loadGroups();
      },
      error: () => this.msg.error('Lỗi khi gỡ nhóm.')
    });
  }

  // --- COOKIE ACTIONS ---
  saveCookie(): void {
    if (!this.cookieInput.trim()) {
      this.msg.warning('Vui lòng dán Cookie Lazada trước khi lưu.');
      return;
    }
    this.savingCookie = true;
    this.api.saveLazadaCookie(this.cookieInput).subscribe({
      next: (res) => {
        this.savingCookie = false;
        this.msg.success(res.message || 'Đã lưu Cookie Lazada thành công!');
        this.cookieInfo = res.info;
        this.cookieInput = '';
      },
      error: (err) => {
        this.savingCookie = false;
        this.msg.error(err.error?.detail || 'Lỗi lưu cookie Lazada.');
      }
    });
  }

  testCookie(): void {
    this.testingCookie = true;
    this.api.testLazadaCookie().subscribe({
      next: (res) => {
        this.testingCookie = false;
        if (res.success) {
          this.msg.success(res.message || 'Kết nối Lazada thành công!');
        } else {
          this.msg.error(res.message || 'Không thể kết nối đến Lazada.');
        }
      },
      error: (err) => {
        this.testingCookie = false;
        this.msg.error('Lỗi kiểm tra kết nối Lazada: ' + (err.error?.detail || err.message));
      }
    });
  }

  // --- CONFIG ACTIONS ---
  saveConfig(): void {
    this.savingConfig = true;
    this.config.selected_groups = this.selectedGroupUrls;
    this.api.updateLazadaHunterConfig(this.config).subscribe({
      next: () => {
        this.savingConfig = false;
        this.msg.success('Đã lưu cấu hình Săn Deal Lazada!');
      },
      error: () => {
        this.savingConfig = false;
        this.msg.error('Lỗi lưu cấu hình.');
      }
    });
  }

  toggleAutoHunter(val: boolean): void {
    this.config.enabled = val;
    this.saveConfig();
  }

  // --- PRODUCT ACTIONS ---
  openAddProductModal(): void {
    this.isEditing = false;
    this.editingProduct = {
      name: '',
      clean_keyword: '',
      avg_price: 100000,
      filter_mall_only: 1,
      min_discount_pct: 10
    };
    this.newProductModalVisible = true;
  }

  openEditProductModal(p: LazadaTrackedProduct): void {
    this.isEditing = true;
    this.editingProduct = { ...p };
    this.newProductModalVisible = true;
  }

  saveProduct(): void {
    if (!this.editingProduct.name || !this.editingProduct.avg_price) {
      this.msg.warning('Vui lòng nhập Tên sản phẩm và Giá trung bình.');
      return;
    }

    if (this.isEditing && this.editingProduct.id) {
      this.api.updateLazadaTrackedProduct(this.editingProduct.id, this.editingProduct).subscribe({
        next: () => {
          this.msg.success('Đã cập nhật sản phẩm.');
          this.newProductModalVisible = false;
          this.loadProducts();
        },
        error: (err) => this.msg.error(err.error?.detail || 'Lỗi cập nhật sản phẩm.')
      });
    } else {
      this.api.createLazadaTrackedProduct(this.editingProduct).subscribe({
        next: () => {
          this.msg.success('Đã thêm sản phẩm theo dõi mới.');
          this.newProductModalVisible = false;
          this.loadProducts();
        },
        error: (err) => this.msg.error(err.error?.detail || 'Lỗi thêm sản phẩm.')
      });
    }
  }

  toggleProduct(p: LazadaTrackedProduct): void {
    this.api.toggleLazadaTrackedProduct(p.id).subscribe({
      next: (res) => {
        p.is_active = res.is_active;
        this.msg.info(p.is_active ? `Đã kích hoạt theo dõi ${p.name}` : `Đã tạm dừng theo dõi ${p.name}`);
      },
      error: () => this.msg.error('Lỗi thay đổi trạng thái sản phẩm.')
    });
  }

  deleteProduct(p: LazadaTrackedProduct): void {
    if (confirm(`Bạn có chắc muốn xóa sản phẩm "${p.name}"?`)) {
      this.api.deleteLazadaTrackedProduct(p.id).subscribe({
        next: () => {
          this.msg.success('Đã xóa sản phẩm.');
          this.loadProducts();
        },
        error: () => this.msg.error('Lỗi xóa sản phẩm.')
      });
    }
  }

  cleaningJunk = false;
  cleanupJunkProducts(): void {
    this.cleaningJunk = true;
    this.api.cleanupJunkLazadaProducts().subscribe({
      next: (res) => {
        this.cleaningJunk = false;
        this.msg.success(res.message || `Đã dọn dẹp ${res.deleted} sản phẩm rác.`);
        this.loadProducts();
      },
      error: () => {
        this.cleaningJunk = false;
        this.msg.error('Lỗi khi dọn dẹp sản phẩm rác.');
      }
    });
  }

  // --- FB SCAN ACTIONS ---
  scanPostsPerGroup: number = 50;

  selectAllHunterGroups(): void {
    this.selectedGroupUrls = this.availableGroups.map(g => g.url);
    this.saveConfig();
    this.msg.info(`Đã chọn toàn bộ ${this.selectedGroupUrls.length} nhóm quét giá.`);
  }

  deselectAllHunterGroups(): void {
    this.selectedGroupUrls = [];
    this.saveConfig();
  }

  toggleGroupSelection(url: string): void {
    const idx = this.selectedGroupUrls.indexOf(url);
    if (idx > -1) {
      this.selectedGroupUrls.splice(idx, 1);
    } else {
      this.selectedGroupUrls.push(url);
    }
    this.saveConfig();
  }

  triggerScanFbNow(): void {
    if (this.selectedGroupUrls.length === 0) {
      this.msg.warning('Vui lòng chọn ít nhất 1 nhóm Facebook để quét bài.');
      return;
    }
    this.scanningFb = true;
    this.api.triggerScanFbMarket(this.selectedGroupUrls, this.selectedAccount, this.scanPostsPerGroup).subscribe({
      next: (res) => {
        if (res.success) {
          this.msg.success(res.message);
          this.pollScanStatus();
        } else {
          this.msg.warning(res.message);
          this.scanningFb = false;
        }
      },
      error: (err) => {
        this.scanningFb = false;
        this.msg.error(err.error?.detail || 'Lỗi kích hoạt quét bài Facebook.');
      }
    });
  }

  pollScanStatus(): void {
    this.api.getScanFbMarketStatus().subscribe({
      next: (res) => {
        this.scanFbStatus = res;
        this.scanningFb = res.is_running;
        if (res.is_running) {
          setTimeout(() => this.pollScanStatus(), 3000);
        } else if (res.last_result) {
          this.loadProducts();
        }
      },
      error: () => {}
    });
  }

  // --- HUNTER ACTIONS ---
  runHunterNow(): void {
    if (this.hunterStatus.is_running) {
      this.msg.warning('Chu kỳ quét deal Lazada hiện đang chạy!');
      return;
    }
    this.runningHunterNow = true;
    this.api.runLazadaHunterNow().subscribe({
      next: (res) => {
        if (res.success) {
          this.msg.success(res.message || 'Đã kích hoạt chu kỳ săn deal Lazada!');
        } else {
          this.msg.warning(res.message);
        }
      },
      error: (err) => {
        this.runningHunterNow = false;
        this.msg.error(err.error?.detail || err.error?.message || 'Lỗi chạy chu kỳ săn deal Lazada.');
      }
    });
  }

  loadHunterLogs(): void {
    this.loadingLogs = true;
    this.api.getLazadaHunterLogs(50).subscribe({
      next: (data) => {
        this.hunterLogs = data;
        this.loadingLogs = false;
      },
      error: () => {
        this.loadingLogs = false;
        this.msg.error('Lỗi tải nhật ký săn deal.');
      }
    });
  }

  clearHunterLogs(): void {
    if (confirm('Bạn có chắc muốn xóa toàn bộ lịch sử log săn deal?')) {
      this.clearingLogs = true;
      this.api.clearLazadaHunterLogs().subscribe({
        next: () => {
          this.clearingLogs = false;
          this.msg.success('Đã xóa toàn bộ lịch sử log.');
          this.loadHunterLogs();
        },
        error: () => {
          this.clearingLogs = false;
          this.msg.error('Lỗi khi xóa log.');
        }
      });
    }
  }

  // --- RADAR SẬP SÀN LOGS & CONFIG ---
  deepDropLogs: any[] = [];
  loadingDeepDropLogs = false;
  clearingDeepDropLogs = false;
  activeLogType: 'hunter' | 'deep_drop' = 'hunter';

  generalConfig: any = {
    enabled: true,
    interval_minutes: 5,
    min_drop_pct: 50.0,
    min_price_floor: 35000.0,
    batch_keywords_per_cycle: 6,
    filter_mall_only: true
  };
  savingGeneralConfig = false;

  loadDeepDropLogs(): void {
    this.loadingDeepDropLogs = true;
    this.api.getDeepDropsLogs(50).subscribe({
      next: (logs) => {
        this.deepDropLogs = logs;
        this.loadingDeepDropLogs = false;
      },
      error: () => {
        this.loadingDeepDropLogs = false;
      }
    });
  }

  clearDeepDropLogs(): void {
    if (confirm('Bạn có chắc muốn xóa toàn bộ lịch sử log Radar Sập Sàn Tmall?')) {
      this.clearingDeepDropLogs = true;
      this.api.clearDeepDropsLogs().subscribe({
        next: () => {
          this.clearingDeepDropLogs = false;
          this.msg.success('Đã xóa toàn bộ lịch sử log Radar.');
          this.loadDeepDropLogs();
        },
        error: () => {
          this.clearingDeepDropLogs = false;
          this.msg.error('Lỗi khi xóa log.');
        }
      });
    }
  }

  loadGeneralConfig(): void {
    this.api.getDeepDropsConfig().subscribe({
      next: (cfg) => (this.generalConfig = { ...this.generalConfig, ...cfg }),
      error: () => {}
    });
  }

  saveGeneralConfig(): void {
    this.savingGeneralConfig = true;
    this.api.updateDeepDropsConfig(this.generalConfig).subscribe({
      next: (res) => {
        this.savingGeneralConfig = false;
        this.msg.success('Đã lưu cấu hình Radar Sập Sàn Tmall (5 phút/lần)!');
      },
      error: () => {
        this.savingGeneralConfig = false;
        this.msg.error('Lỗi lưu cấu hình Radar.');
      }
    });
  }

  // --- RADAR KHO TỪ KHÓA & NGÀNH HÀNG MANAGEMENT ---
  radarCategories: RadarCategoryItem[] = [];
  totalRadarCategories = 0;
  totalRadarKeywords = 0;
  loadingRadarCategories = false;
  syncingLazadaCategories = false;
  resettingRadarCategories = false;

  manageCategoriesModalVisible = false;
  categoryModalVisible = false;
  isEditingCategory = false;
  editingCategory: RadarCategoryItem = { id: '', name: '', icon: '🏷️', keywords: [], is_active: true };
  editingKeywordsText = '';
  savingCategory = false;

  loadRadarCategories(): void {
    this.loadingRadarCategories = true;
    this.api.getRadarCategories().subscribe({
      next: (res) => {
        this.radarCategories = res.categories || [];
        this.totalRadarCategories = res.total_categories || this.radarCategories.length;
        this.totalRadarKeywords = res.total_keywords || 0;
        this.loadingRadarCategories = false;
      },
      error: () => (this.loadingRadarCategories = false)
    });
  }

  syncCategoriesFromLazada(): void {
    this.syncingLazadaCategories = true;
    this.api.syncLazadaCategories().subscribe({
      next: (res) => {
        this.syncingLazadaCategories = false;
        this.msg.success(res.message || 'Đã đồng bộ danh mục từ Lazada thành công!');
        this.loadRadarCategories();
      },
      error: (err) => {
        this.syncingLazadaCategories = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi đồng bộ danh mục Lazada.');
      }
    });
  }

  resetRadarCategoriesToDefault(): void {
    this.modal.confirm({
      nzTitle: 'Khôi phục kho từ khóa Radar về mặc định?',
      nzContent: 'Hệ thống sẽ nạp lại 13 ngành hàng chuẩn và 260 từ khóa săn deal chính hãng.',
      nzOkText: 'Khôi phục',
      nzOkDanger: true,
      nzOnOk: () => {
        this.resettingRadarCategories = true;
        this.api.resetRadarCategories().subscribe({
          next: (res) => {
            this.resettingRadarCategories = false;
            this.msg.success(res.message || 'Đã khôi phục kho từ khóa chuẩn thành công!');
            this.loadRadarCategories();
          },
          error: () => {
            this.resettingRadarCategories = false;
            this.msg.error('Lỗi khi khôi phục kho từ khóa.');
          }
        });
      }
    });
  }

  openManageCategoriesModal(): void {
    this.manageCategoriesModalVisible = true;
    this.loadRadarCategories();
  }

  openAddCategoryModal(): void {
    this.isEditingCategory = false;
    this.editingCategory = {
      id: '',
      name: '',
      icon: '🏷️',
      keywords: [],
      is_active: true,
      sort_order: this.radarCategories.length + 1
    };
    this.editingKeywordsText = '';
    this.categoryModalVisible = true;
  }

  openEditCategoryModal(cat: RadarCategoryItem): void {
    this.isEditingCategory = true;
    this.editingCategory = { ...cat, keywords: [...cat.keywords] };
    this.editingKeywordsText = (cat.keywords || []).join('\n');
    this.categoryModalVisible = true;
  }

  saveRadarCategory(): void {
    if (!this.editingCategory.name.trim()) {
      this.msg.warning('Vui lòng nhập tên ngành hàng.');
      return;
    }
    const kws = this.editingKeywordsText
      .split('\n')
      .map(k => k.trim())
      .filter(k => k.length > 0);
    if (kws.length === 0) {
      this.msg.warning('Vui lòng nhập ít nhất 1 từ khóa (mỗi dòng 1 từ khóa).');
      return;
    }
    this.editingCategory.keywords = kws;
    this.savingCategory = true;
    this.api.saveRadarCategory(this.editingCategory).subscribe({
      next: (res) => {
        this.savingCategory = false;
        this.msg.success(res.message || 'Đã lưu ngành hàng thành công!');
        this.categoryModalVisible = false;
        this.loadRadarCategories();
      },
      error: (err) => {
        this.savingCategory = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi lưu ngành hàng.');
      }
    });
  }

  deleteRadarCategory(catId: string, event?: Event): void {
    if (event) event.stopPropagation();
    this.modal.confirm({
      nzTitle: 'Xác nhận xóa ngành hàng này khỏi Radar?',
      nzContent: 'Ngành hàng và các từ khóa liên quan sẽ bị gỡ khỏi chu kỳ quét radar.',
      nzOkText: 'Xóa ngay',
      nzOkDanger: true,
      nzOnOk: () => {
        this.api.deleteRadarCategory(catId).subscribe({
          next: (res) => {
            this.msg.success(res.message || 'Đã xóa ngành hàng.');
            this.loadRadarCategories();
          },
          error: () => this.msg.error('Lỗi khi xóa ngành hàng.')
        });
      }
    });
  }

  toggleRadarCategoryActive(cat: RadarCategoryItem): void {
    const updated = !cat.is_active;
    cat.is_active = updated;
    this.api.saveRadarCategory({ ...cat, is_active: updated }).subscribe({
      next: () => {
        this.msg.success(`Đã ${updated ? 'bật' : 'tắt'} ngành "${cat.name}".`);
      },
      error: () => {
        cat.is_active = !updated;
        this.msg.error('Lỗi khi cập nhật trạng thái ngành hàng.');
      }
    });
  }

  getCategoryDealCount(catName: string): number {
    if (!this.deepDrops) return 0;
    const norm = catName.toLowerCase().trim();
    return this.deepDrops.filter(d => (d.category || '').toLowerCase().trim().includes(norm) || norm.includes((d.category || '').toLowerCase().trim())).length;
  }

  // --- TEST SEARCH MODAL ---
  hasSearched = false;

  openTestSearch(keyword?: string, filterMall: boolean = false): void {
    this.testKeyword = keyword || '';
    this.testFilterMall = filterMall;
    this.testSearchResults = [];
    this.hasSearched = false;
    this.testSearchModalVisible = true;
    if (this.testKeyword) {
      this.doTestSearch();
    }
  }

  doTestSearch(): void {
    if (!this.testKeyword.trim()) {
      this.msg.warning('Vui lòng nhập từ khóa tìm kiếm.');
      return;
    }
    this.testSearching = true;
    this.hasSearched = true;
    this.api.testSearchLazada(this.testKeyword.trim(), this.testFilterMall).subscribe({
      next: (res) => {
        this.testSearching = false;
        this.testSearchResults = res.items || [];
        if (this.testSearchResults.length === 0) {
          if (this.testFilterMall) {
            this.msg.warning(`Không tìm thấy gian hàng LazMall cho "${this.testKeyword}". Hãy thử tắt "CHỈ LAZMALL" để xem các shop thường!`);
          } else {
            this.msg.info(`Không tìm thấy sản phẩm nào trên Lazada với từ khóa "${this.testKeyword}".`);
          }
        } else {
          this.msg.success(`Đã tìm thấy ${this.testSearchResults.length} sản phẩm trên Lazada!`);
        }
      },
      error: (err) => {
        this.testSearching = false;
        this.msg.error(err.error?.detail || 'Lỗi tìm kiếm Lazada.');
      }
    });
  }

  retryTestWithoutMall(): void {
    this.testFilterMall = false;
    this.doTestSearch();
  }

  formatTime(ts: number | null | undefined): string {
    if (!ts) return 'Chưa có';
    const d = new Date(ts * 1000);
    return d.toLocaleString('vi-VN');
  }

  get filteredProducts(): LazadaTrackedProduct[] {
    if (!this.productSearch.trim()) return this.products;
    const q = this.productSearch.toLowerCase();
    return this.products.filter(
      (p) => p.name.toLowerCase().includes(q) || (p.clean_keyword && p.clean_keyword.toLowerCase().includes(q))
    );
  }

  get activeProductsCount(): number {
    return this.products.filter((p) => p.is_active).length;
  }

  // --- TMALL BRAND DIRECTORY & SHOP METHODS ---
  loadTmallCategories(): void {
    this.tmallCategoriesLoading = true;
    this.api.getTmallCategories().subscribe({
      next: (res) => {
        this.tmallCategories = res.categories || [];
        this.tmallCategoriesLoading = false;
        if (this.tmallCategories.length > 0) {
          // Nếu category hiện tại chưa chọn hoặc không có, chọn nhóm đầu tiên trong priority
          const hasCurrent = this.tmallCategories.some(c => c.id === this.selectedTmallCategoryId);
          if (!hasCurrent) {
            const firstPriority = this.tmallCategories.find(c => this.isPriorityCategory(c.name));
            this.selectedTmallCategoryId = firstPriority ? firstPriority.id : this.tmallCategories[0].id;
          }
          if (this.selectedTmallCategoryId) {
            this.loadTmallShops(this.selectedTmallCategoryId);
          }
        }
      },
      error: () => (this.tmallCategoriesLoading = false)
    });
  }

  selectTmallCategory(catId: string): void {
    this.selectedTmallCategoryId = catId;
    this.tmallShopSearch = '';
    this.loadTmallShops(catId);
  }

  loadTmallShops(catId: string): void {
    this.tmallShopsLoading = true;
    this.api.getTmallShops(catId, false, 500).subscribe({
      next: (res) => {
        this.tmallShops = res.shops || [];
        this.tmallShopsLoading = false;
      },
      error: () => (this.tmallShopsLoading = false)
    });
  }

  toggleTmallCategoryActive(cat: TmallCategoryItem, event?: Event): void {
    if (event) event.stopPropagation();
    const newActive = cat.is_active === 1 ? 0 : 1;
    cat.is_active = newActive;
    this.api.toggleTmallCategory(cat.id, newActive === 1).subscribe({
      next: () => {
        this.msg.success(`Đã ${newActive === 1 ? 'bật' : 'tắt'} nhóm ngành "${cat.name}".`);
      },
      error: () => {
        cat.is_active = newActive === 1 ? 0 : 1;
        this.msg.error('Lỗi khi bật/tắt nhóm ngành Tmall.');
      }
    });
  }

  syncTmallBrandsNow(): void {
    this.syncingTmallBrands = true;
    this.api.syncTmallBrands().subscribe({
      next: (res) => {
        this.syncingTmallBrands = false;
        if (res.success) {
          this.msg.success(res.message || 'Đã đồng bộ danh mục Brand Tmall thành công!');
          this.loadTmallCategories();
        } else {
          this.msg.warning(res.message || 'Không thể đồng bộ Brand Tmall.');
        }
      },
      error: () => {
        this.syncingTmallBrands = false;
        this.msg.error('Lỗi kết nối khi đồng bộ Brand Tmall.');
      }
    });
  }

  triggerTmallBrandScanNow(specificCategoryIds?: string[]): void {
    this.runningTmallScanNow = true;
    const cats = specificCategoryIds || (this.selectedTmallCategoryId ? [this.selectedTmallCategoryId] : undefined);
    this.api.triggerTmallBrandScan({ categories: cats, min_drop_pct: this.tmallMinDropPct, max_pages: 1 }).subscribe({
      next: (res) => {
        this.runningTmallScanNow = false;
        if (res.success) {
          this.msg.success(res.message || 'Đã bắt đầu quét các shop Tmall trong nền!');
        } else {
          this.msg.info(res.message || 'Radar Tmall đang chạy.');
        }
      },
      error: (err) => {
        this.runningTmallScanNow = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi kích hoạt quét Brand Tmall.');
      }
    });
  }

  triggerScanAllPriorityCategories(): void {
    const priorityCatIds = this.tmallCategories
      .filter(c => this.isPriorityCategory(c.name))
      .map(c => c.id);
    this.triggerTmallBrandScanNow(priorityCatIds);
  }

  // --- CONTINUOUS RUNNER (QUÉT TUẦN TỰ LIÊN TỤC NGÀY ĐÊM) ---
  toggleContinuousScan(): void {
    if (this.tmallStatus.continuous_mode) {
      this.stopContinuousScan();
    } else {
      this.startContinuousScan();
    }
  }

  startContinuousScan(categoryIds?: string[]): void {
    const cats = categoryIds || (this.tmallCategories.filter(c => c.is_active === 1).map(c => c.id));
    this.api.startTmallContinuousScan({ categories: cats, min_drop_pct: this.tmallMinDropPct, max_pages: 1 }).subscribe({
      next: (res) => {
        if (res.success) {
          this.msg.success(res.message || 'Đã kích hoạt chế độ quét tuần tự liên tục!');
        } else {
          this.msg.info(res.message || 'Radar đang hoạt động.');
        }
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi kích hoạt chế độ quét liên tục.');
      }
    });
  }

  stopContinuousScan(): void {
    this.api.stopTmallContinuousScan().subscribe({
      next: (res) => {
        this.msg.warning(res.message || 'Đã gửi yêu cầu dừng quét liên tục.');
      },
      error: () => this.msg.error('Lỗi khi gửi yêu cầu dừng.')
    });
  }
}

