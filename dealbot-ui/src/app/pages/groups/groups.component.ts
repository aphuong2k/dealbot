import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, GroupItem, ScannedGroup, EvaluatedGroup, PostItem, TestPostPayload, TestPostResult, DealItem } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzPopconfirmModule } from 'ng-zorro-antd/popconfirm';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';

@Component({
  selector: 'app-groups',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzInputModule,
    NzSelectModule,
    NzTagModule,
    NzSwitchModule,
    NzProgressModule,
    NzSpinModule,
    NzTabsModule,
    NzModalModule,
    NzEmptyModule,
    NzBadgeModule,
    NzPopconfirmModule,
    NzToolTipModule,
    NzCheckboxModule
  ],
  templateUrl: './groups.component.html',
  styleUrls: ['./groups.component.css']
})
export class GroupsComponent implements OnInit {
  groups: GroupItem[] = [];
  loading = false;
  discoverLoading = false;
  // --- MAIN NAVIGATION TABS ---
  activeMainTab: 'groups' | 'schedule' | 'manual' | 'auto' = 'groups';

  // --- POSTS SCHEDULE STATE ---
  posts: PostItem[] = [];
  postsLoading = false;
  planLoading = false;
  runDueLoading = false;
  runningPostId: number | null = null;
  selectedPostStatus = '';
  selectedPostAccount = '';
  selectedPostForPreview: PostItem | null = null;
  previewModalVisible = false;

  postStatusOptions = [
    { label: 'Tất cả trạng thái', value: '' },
    { label: '⏳ Đang chờ (Queued)', value: 'queued' },
    { label: '✅ Đã đăng (Done)', value: 'done' },
    { label: '⏳ Chờ admin duyệt (Pending)', value: 'pending_approval' },
    { label: '❌ Thất bại (Failed)', value: 'failed' },
    { label: '⏭ Bỏ qua (Skipped)', value: 'skipped' }
  ];

  postAccountOptions = [
    { label: 'Tất cả nick', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  // --- MANUAL POST STUDIO STATE ---
  manualLoading = false;
  manualResult: TestPostResult | null = null;
  activeJoinedGroups: GroupItem[] = [];
  availableDeals: DealItem[] = [];
  dealsLoading = false;
  selectedDealId = '';
  selectedDeal: DealItem | null = null;
  dealSearchQuery = '';

  manualForm: TestPostPayload = {
    account: 'nick_a',
    group_url: '',
    caption: '🔥 DEAL HOT GIẢM SỐC HÔM NAY!\nSăn ngay giá siêu hời chỉ trong khung giờ vàng, số lượng có hạn anh em ơi!',
    comment: '👉 Link mua sản phẩm chính hãng: https://s.shopee.vn/test-deal-bot\nTham gia nhóm Telegram nhận deal sớm: https://t.me/san_sale_shopee',
    dry_run: true,
    image_path: ''
  };

  // --- AUTO PILOT STATE ---
  pipelineLoading = false;
  pipelineResult: any = null;

  // --- GROUPS STATE ---
  selectedTab = 'all';
  searchQuery = '';
  selectedKind = '';
  selectedAccountFilter = 'all';

  accountOptions = [
    { label: 'Chưa gán', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  // Niche Evaluation & Search
  nicheSearchModalVisible = false;
  nicheSearchLoading = false;
  nicheSearchAccount = 'nick_a';
  nicheSearchCategory = 'Thời Trang Nam';
  nicheSearchKeyword = 'hội phối đồ nam';
  nicheMinMembers = 5000;
  nicheMinPostsPerDay = 3;
  nicheOnlyPublic = true;
  nicheAutoJoin = false;
  evaluatedGroups: EvaluatedGroup[] = [];
  nicheSearchResultMessage = '';
  joiningEvaluatedUrl = '';
  importingEvaluated = false;

  recommendedKeywords: string[] = [
    'hội phối đồ nam',
    'thời trang nam',
    'outfit nam chất',
    'nghiện phối đồ nam',
    'săn sale thời trang nam',
    'hội mặc đẹp nam giới'
  ];

  nichePresets = [
    { 
      label: 'Thời trang nam', 
      value: 'Thời Trang Nam', 
      defaultKw: 'hội phối đồ nam',
      recommendedKeywords: [
        'hội phối đồ nam',
        'thời trang nam',
        'outfit nam chất',
        'nghiện phối đồ nam',
        'săn sale thời trang nam',
        'hội mặc đẹp nam giới'
      ]
    },
    { 
      label: 'Thời trang nữ', 
      value: 'Thời Trang Nữ', 
      defaultKw: 'hội review thời trang nữ',
      recommendedKeywords: [
        'hội review thời trang nữ',
        'hội phối đồ nữ',
        'outfit nữ xinh',
        'hội săn sale quần áo nữ',
        'nghiện mặc đẹp & phối đồ',
        'order taobao thời trang nữ'
      ]
    },
    { 
      label: 'Mỹ phẩm / Skincare', 
      value: 'mỹ phẩm', 
      defaultKw: 'hội review mỹ phẩm',
      recommendedKeywords: [
        'hội review mỹ phẩm',
        'hội nghiện skincare & làm đẹp',
        'review mỹ phẩm có tâm',
        'săn sale mỹ phẩm chính hãng',
        'hội trang điểm & makeup',
        'chăm sóc da & làm đẹp'
      ]
    },
    { 
      label: 'Gia dụng / Nhà cửa', 
      value: 'gia dụng', 
      defaultKw: 'hội yêu bếp nghiện nhà',
      recommendedKeywords: [
        'hội yêu bếp nghiện nhà',
        'đồ gia dụng thông minh',
        'review đồ gia dụng',
        'săn sale đồ bếp & gia dụng',
        'mẹo vặt gia đình & đồ tiện ích',
        'nghiện decor nhà & đồ gia dụng'
      ]
    },
    { 
      label: 'Mẹ & Bé', 
      value: 'mẹ và bé', 
      defaultKw: 'hội mẹ và bé',
      recommendedKeywords: [
        'hội mẹ và bé',
        'hội các mẹ bỉm sữa',
        'kinh nghiệm chăm con & săn deal mẹ bé',
        'review bỉm sữa ăn dặm',
        'thanh lý & săn sale đồ mẹ bé',
        'nuôi con khoa học & ăn dặm'
      ]
    },
    { 
      label: 'Đồ công nghệ', 
      value: 'đồ công nghệ giá rẻ', 
      defaultKw: 'hội săn deal công nghệ',
      recommendedKeywords: [
        'hội săn deal công nghệ',
        'cộng đồng setup góc làm việc',
        'review đồ công nghệ giá rẻ',
        'hội tai nghe bàn phím chuột',
        'phụ kiện điện thoại máy tính',
        'hội đam mê đồ công nghệ'
      ]
    },
    { 
      label: 'Săn sale tổng hợp', 
      value: 'săn sale shopee', 
      defaultKw: 'hội săn sale shopee',
      recommendedKeywords: [
        'hội săn sale shopee',
        'chia sẻ mã giảm giá voucher shopee',
        'săn deal 0đ 1k',
        'nghiện săn deal giá rẻ',
        'hội chia sẻ mã voucher',
        'săn sale shopee lazada tiki'
      ]
    }
  ];

  // Group Scanner
  scanModalVisible = false;
  scanLoading = false;
  scanAccount = '';
  scannedGroups: ScannedGroup[] = [];
  scannedMessage = '';
  scannedSearchQuery = '';

  // Leave group
  leavingGroupUrl = '';

  // Auto Join Groups
  autoJoinModalVisible = false;
  autoJoinAccount = 'nick_a';
  autoJoinLimit = 5;
  autoJoinLoading = false;
  autoJoinResult: any = null;
  joiningGroupUrl = '';


  constructor(
    private api: ApiService,
    private msg: NzMessageService,
    private modal: NzModalService,
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      const tab = params['tab'];
      if (tab && ['groups', 'schedule', 'manual', 'auto'].includes(tab)) {
        this.activeMainTab = tab as any;
      }
    });

    this.fetchGroups();
    this.fetchPosts();
    this.loadActiveGroupsForManual();
    this.loadDealsForManual();
  }

  fetchGroups(): void {
    this.loading = true;
    const statusParam = this.selectedTab === 'all' ? undefined : this.selectedTab;
    const accountParam = this.selectedAccountFilter === 'all' ? undefined : this.selectedAccountFilter;
    this.api.getGroups(statusParam, this.selectedKind || undefined, this.searchQuery || undefined, accountParam).subscribe({
      next: (data) => {
        this.groups = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải danh sách nhóm!');
      }
    });
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedAccountFilter = 'all';
    this.fetchGroups();
  }

  onTabChange(index: number): void {
    const tabs = ['all', 'candidate', 'joined', 'cooling_down', 'banned'];
    this.selectedTab = tabs[index] || 'all';
    this.fetchGroups();
  }

  get filteredScannedGroups(): ScannedGroup[] {
    if (!this.scannedSearchQuery.trim()) return this.scannedGroups;
    const q = this.scannedSearchQuery.toLowerCase();
    return this.scannedGroups.filter(g => (g.name || '').toLowerCase().includes(q) || (g.url || '').toLowerCase().includes(q));
  }

  updateStatus(g: GroupItem, newStatus: any): void {
    this.api.updateGroup(g.url, { status: newStatus }).subscribe({
      next: () => {
        g.status = newStatus;
        if (newStatus === 'joined') g.consecutive_fails = 0;
        this.msg.success(`Đã cập nhật trạng thái nhóm sang "${newStatus}"!`);
      },
      error: () => this.msg.error('Lỗi khi cập nhật trạng thái nhóm!')
    });
  }

  onAllowLinkChange(g: GroupItem, checked: boolean): void {
    const val = checked ? 1 : 0;
    this.api.updateGroup(g.url, { allow_link: val }).subscribe({
      next: () => {
        g.allow_link = val;
        this.msg.success(`Đã ${checked ? 'cho phép' : 'chặn'} link comment nhóm!`);
      },
      error: () => this.msg.error('Lỗi cập nhật cài đặt link!')
    });
  }

  onAccountChange(g: GroupItem, acc: string): void {
    this.api.updateGroup(g.url, { account: acc }).subscribe({
      next: () => {
        g.account = acc;
        this.msg.success(`Đã gán cố định nhóm cho ${acc}!`);
      },
      error: () => this.msg.error('Lỗi khi gán nick!')
    });
  }

  triggerDiscover(): void {
    this.discoverLoading = true;
    this.api.discoverGroups().subscribe({
      next: (res) => {
        this.discoverLoading = false;
        this.msg.success(res.message);
        setTimeout(() => this.fetchGroups(), 3000);
      },
      error: () => {
        this.discoverLoading = false;
        this.msg.error('Lỗi khi quét nhóm mới!');
      }
    });
  }

  // --- SCAN JOINED GROUPS ---
  openScanModal(): void {
    this.scanModalVisible = true;
    this.scannedGroups = [];
    this.scannedMessage = '';
    this.scanAccount = this.accountOptions.length > 1 ? this.accountOptions[1].value : '';
  }

  closeScanModal(): void {
    this.scanModalVisible = false;
  }

  startScan(): void {
    if (!this.scanAccount) {
      this.msg.warning('Vui lòng chọn tài khoản để quét!');
      return;
    }
    this.scanLoading = true;
    this.scannedGroups = [];
    this.scannedMessage = '';
    this.api.scanJoinedGroups(this.scanAccount).subscribe({
      next: (res) => {
        this.scanLoading = false;
        this.scannedGroups = res.groups || [];
        this.scannedMessage = res.message;
        if (res.success) {
          this.msg.success(res.message);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.scanLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi quét danh sách group!');
      }
    });
  }

  // --- LEAVE GROUP ---
  confirmLeaveGroup(g: GroupItem): void {
    if (!g.account) {
      this.msg.warning('Nhóm chưa được gán nick! Hãy chọn nick trước khi rời nhóm.');
      return;
    }
    this.leavingGroupUrl = g.url;
    this.api.leaveGroup(g.account, g.url).subscribe({
      next: (res) => {
        this.leavingGroupUrl = '';
        if (res.success) {
          this.msg.success(res.message);
          g.status = 'skip' as any;
          // Refresh danh sách
          setTimeout(() => this.fetchGroups(), 1000);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.leavingGroupUrl = '';
        this.msg.error(err?.error?.detail || 'Lỗi khi rời nhóm!');
      }
    });
  }

  leaveScannedGroup(sg: ScannedGroup): void {
    if (!this.scanAccount) {
      this.msg.warning('Không xác định được nick!');
      return;
    }
    this.leavingGroupUrl = sg.url;
    this.api.leaveGroup(this.scanAccount, sg.url).subscribe({
      next: (res) => {
        this.leavingGroupUrl = '';
        if (res.success) {
          this.msg.success(res.message);
          // Xóa khỏi danh sách hiển thị
          this.scannedGroups = this.scannedGroups.filter(g => g.url !== sg.url);
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.leavingGroupUrl = '';
        this.msg.error(err?.error?.detail || 'Lỗi khi rời nhóm!');
      }
    });
  }

  // --- REMOVE GROUP FROM DB ---
  removeGroupFromDb(g: GroupItem): void {
    this.api.removeGroupFromDb(g.url).subscribe({
      next: (res) => {
        this.msg.success(res.message);
        this.groups = this.groups.filter(item => item.url !== g.url);
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi xóa group!');
      }
    });
  }

  // --- IMPORT SCANNED GROUPS TO DB ---
  importLoading = false;

  importGroup(sg: ScannedGroup): void {
    const payload = [{
      url: sg.url,
      name: sg.name,
      account: this.scanAccount || '',
      status: 'joined',
      kind: (sg.kind as any) || 'dealhunt',
      niche: sg.niche || 'săn sale'
    }];
    this.api.importScannedGroups(payload).subscribe({
      next: (res) => {
        this.msg.success(`Đã thêm "${sg.name || sg.url}" vào bot!`);
        this.fetchGroups();
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi thêm nhóm vào bot!');
      }
    });
  }

  importAllScanned(): void {
    if (this.scannedGroups.length === 0) return;
    this.importLoading = true;
    const payload = this.scannedGroups.map(sg => ({
      url: sg.url,
      name: sg.name,
      account: this.scanAccount || '',
      status: 'joined',
      kind: sg.kind || 'dealhunt',
      niche: sg.niche || 'săn sale'
    }));
    this.api.importScannedGroups(payload).subscribe({
      next: (res) => {
        this.importLoading = false;
        this.msg.success(res.message);
        this.fetchGroups();
      },
      error: (err) => {
        this.importLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi nhập danh sách nhóm!');
      }
    });
  }

  isGroupInDb(sg: ScannedGroup): boolean {
    return this.groups.some(g => g.url === sg.url);
  }

  // --- AUTO JOIN GROUP METHODS ---
  get candidateGroups(): GroupItem[] {
    return this.groups.filter(g => g.status === 'candidate');
  }

  openAutoJoinModal(): void {
    this.autoJoinModalVisible = true;
    this.autoJoinResult = null;
  }

  closeAutoJoinModal(): void {
    this.autoJoinModalVisible = false;
  }

  joinSingleGroup(g: GroupItem): void {
    const acc = g.account || this.autoJoinAccount || 'nick_a';
    this.joiningGroupUrl = g.url;
    this.api.joinGroup(acc, g.url).subscribe({
      next: (res) => {
        this.joiningGroupUrl = '';
        if (res.success) {
          this.msg.success(res.message || `Đã tham gia nhóm ${g.name || g.url}!`);
          g.status = (res.status === 'pending_approval' ? 'candidate' : 'joined') as any;
          this.fetchGroups();
        } else {
          this.msg.warning(res.message || 'Không thể tham gia nhóm.');
        }
      },
      error: (err) => {
        this.joiningGroupUrl = '';
        const msg = err?.error?.detail || 'Lỗi khi yêu cầu bot tham gia nhóm!';
        this.msg.error(msg);
      }
    });
  }

  runAutoJoinBatch(): void {
    this.autoJoinLoading = true;
    this.autoJoinResult = null;

    this.api.autoJoinBatch(this.autoJoinAccount, this.autoJoinLimit).subscribe({
      next: (res) => {
        this.autoJoinLoading = false;
        this.autoJoinResult = res;
        if (res.success) {
          this.msg.success(res.message || 'Hoàn tất quy trình tự động tham gia nhóm!');
          this.fetchGroups();
        } else {
          this.msg.warning(res.message || 'Có cảnh báo khi tham gia nhóm.');
        }
      },
      error: (err) => {
        this.autoJoinLoading = false;
        const msg = err?.error?.detail || 'Lỗi khi gọi bot auto-join!';
        this.msg.error(msg);
      }
    });
  }

  // --- NICHE SEARCH & GROUP EVALUATION ---
  openNicheSearchModal(): void {
    this.nicheSearchModalVisible = true;
    this.evaluatedGroups = [];
    this.nicheSearchResultMessage = '';
    this.nicheSearchAccount = this.accountOptions.length > 1 ? this.accountOptions[1].value : 'nick_a';
    this.onNichePresetChange(this.nicheSearchCategory);
  }

  closeNicheSearchModal(): void {
    this.nicheSearchModalVisible = false;
  }

  onNichePresetChange(category: string): void {
    this.nicheSearchCategory = category;
    const found = this.nichePresets.find(p => p.value.toLowerCase() === category.toLowerCase());
    if (found) {
      this.recommendedKeywords = found.recommendedKeywords || [found.defaultKw];
      this.nicheSearchKeyword = found.defaultKw;
    } else {
      this.recommendedKeywords = [
        `hội review ${category}`,
        `hội ${category}`,
        `săn sale ${category}`,
        `kinh nghiệm mua ${category}`
      ];
      this.nicheSearchKeyword = `hội review ${category}`;
    }
  }

  selectRecommendedKeyword(kw: string): void {
    this.nicheSearchKeyword = kw;
  }

  startNicheSearch(): void {
    if (!this.nicheSearchAccount) {
      this.msg.warning('Vui lòng chọn tài khoản Facebook để thực hiện tìm kiếm!');
      return;
    }
    if (!this.nicheSearchKeyword.trim()) {
      this.msg.warning('Vui lòng nhập từ khóa tìm kiếm nhóm!');
      return;
    }

    this.nicheSearchLoading = true;
    this.evaluatedGroups = [];
    this.nicheSearchResultMessage = '';

    this.api.searchNicheGroups({
      account: this.nicheSearchAccount,
      keyword: this.nicheSearchKeyword.trim(),
      niche: this.nicheSearchCategory,
      min_members: this.nicheMinMembers,
      min_posts_per_day: this.nicheMinPostsPerDay,
      only_public: this.nicheOnlyPublic,
      auto_join: this.nicheAutoJoin,
      max_results: 15,
      max_scroll: 6
    }).subscribe({
      next: (res) => {
        this.nicheSearchLoading = false;
        if (res.success) {
          this.evaluatedGroups = res.groups || [];
          this.nicheSearchResultMessage = res.message;
          this.msg.success(res.message);
          if (this.nicheAutoJoin) {
            this.fetchGroups();
          }
        } else {
          this.msg.error(res.message);
        }
      },
      error: (err) => {
        this.nicheSearchLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi quét và đánh giá nhóm!');
      }
    });
  }

  joinEvaluatedGroup(eg: EvaluatedGroup): void {
    this.joiningEvaluatedUrl = eg.url;
    this.api.joinGroup(this.nicheSearchAccount, eg.url).subscribe({
      next: (res) => {
        this.joiningEvaluatedUrl = '';
        if (res.success) {
          this.msg.success(res.message || `Đã tham gia nhóm ${eg.name}!`);
          eg.status = res.status || 'joined';
          // Tự động lưu vào DB
          this.api.importScannedGroups([{
            url: eg.url,
            name: eg.name,
            account: this.nicheSearchAccount,
            status: eg.status,
            niche: eg.niche,
            kind: eg.kind,
            members: eg.members,
            posts_per_day: eg.posts_per_day,
            activity_text: eg.activity_text,
            privacy: eg.privacy,
            priority_score: eg.priority_score
          }]).subscribe(() => this.fetchGroups());
        } else {
          this.msg.warning(res.message);
        }
      },
      error: (err) => {
        this.joiningEvaluatedUrl = '';
        this.msg.error(err?.error?.detail || 'Lỗi khi tham gia nhóm!');
      }
    });
  }

  importAllQualifiedEvaluated(): void {
    const qualified = this.evaluatedGroups.filter(g => g.is_qualified);
    if (qualified.length === 0) {
      this.msg.warning('Không có nhóm nào đạt chuẩn tiêu chí để nhập!');
      return;
    }
    this.importingEvaluated = true;
    const payload = qualified.map(g => ({
      url: g.url,
      name: g.name,
      account: this.nicheSearchAccount,
      status: g.status || 'candidate',
      niche: g.niche,
      kind: g.kind,
      members: g.members,
      posts_per_day: g.posts_per_day,
      activity_text: g.activity_text,
      privacy: g.privacy,
      priority_score: g.priority_score
    }));

    this.api.importScannedGroups(payload).subscribe({
      next: (res) => {
        this.importingEvaluated = false;
        this.msg.success(`Đã thêm ${qualified.length} nhóm đạt chuẩn vào danh sách quản lý!`);
        this.fetchGroups();
      },
      error: (err) => {
        this.importingEvaluated = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi nhập danh sách nhóm!');
      }
    });
  }

  // ==========================================
  // --- MAIN TAB SWITCHING & SYNC ---
  // ==========================================
  switchMainTab(tab: 'groups' | 'schedule' | 'manual' | 'auto'): void {
    this.activeMainTab = tab;
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge'
    });
    if (tab === 'schedule') {
      this.fetchPosts();
    } else if (tab === 'manual') {
      this.loadActiveGroupsForManual();
      this.loadDealsForManual();
    } else if (tab === 'auto') {
      this.fetchPosts();
    }
  }

  // ==========================================
  // --- POSTS SCHEDULE LOGIC ---
  // ==========================================
  get postsQueuedCount(): number {
    return this.posts.filter(p => p.status === 'queued').length;
  }

  get postsDoneCount(): number {
    return this.posts.filter(p => p.status === 'done').length;
  }

  get postsPendingCount(): number {
    return this.posts.filter(p => p.status === 'pending_approval').length;
  }

  get postsFailedCount(): number {
    return this.posts.filter(p => p.status === 'failed').length;
  }

  get postsSkippedCount(): number {
    return this.posts.filter(p => p.status === 'skipped').length;
  }

  get todayTimelinePosts(): PostItem[] {
    return [...this.posts].sort((a, b) => a.scheduled_at - b.scheduled_at);
  }

  fetchPosts(): void {
    this.postsLoading = true;
    this.api.getPosts(this.selectedPostStatus || undefined, this.selectedPostAccount || undefined).subscribe({
      next: (data) => {
        this.posts = data;
        this.postsLoading = false;
      },
      error: () => {
        this.postsLoading = false;
        this.msg.error('Không thể tải lịch trình bài đăng!');
      }
    });
  }

  triggerPlan(): void {
    this.planLoading = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.planLoading = false;
        this.msg.success(res.message);
        this.fetchPosts();
      },
      error: (err) => {
        this.planLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi lập lịch hôm nay!');
      }
    });
  }

  triggerRunDue(): void {
    this.runDueLoading = true;
    this.api.runDuePosts().subscribe({
      next: (res) => {
        this.runDueLoading = false;
        this.msg.success(res.message);
        setTimeout(() => this.fetchPosts(), 3000);
      },
      error: (err) => {
        this.runDueLoading = false;
        this.msg.error(err?.error?.detail || 'Lỗi khi kích hoạt phiên đăng bài!');
      }
    });
  }

  runNowPost(post: PostItem): void {
    if (!confirm(`Bạn có chắc muốn đăng ngay bài viết #${post.id} lên nhóm này?`)) return;
    this.runningPostId = post.id;
    this.api.runSinglePost(post.id).subscribe({
      next: (res) => {
        this.runningPostId = null;
        this.msg.success(res.message);
        this.fetchPosts();
        if (this.previewModalVisible) {
          this.closePreview();
        }
      },
      error: (err) => {
        this.runningPostId = null;
        const msg = err?.error?.detail || 'Lỗi khi đăng bài!';
        this.msg.error(msg);
      }
    });
  }

  viewPost(post: PostItem): void {
    this.selectedPostForPreview = post;
    this.previewModalVisible = true;
  }

  closePreview(): void {
    this.previewModalVisible = false;
    this.selectedPostForPreview = null;
  }

  extractAffLink(text?: string): string {
    if (!text) return '';
    const m = text.match(/https?:\/\/[^\s]+/);
    return m ? m[0] : '';
  }

  copyLink(link: string): void {
    if (!link) return;
    navigator.clipboard.writeText(link);
    this.msg.success('Đã sao chép link vào Clipboard!');
  }

  // ==========================================
  // --- MANUAL POST STUDIO LOGIC ---
  // ==========================================
  loadActiveGroupsForManual(): void {
    this.api.getGroups().subscribe({
      next: (groups) => {
        this.activeJoinedGroups = groups.filter(g => g.status === 'joined' || g.status === 'approved' || g.status === 'candidate');
        if (this.activeJoinedGroups.length > 0 && !this.manualForm.group_url) {
          this.manualForm.group_url = this.activeJoinedGroups[0].url;
          if (this.activeJoinedGroups[0].account) {
            this.manualForm.account = this.activeJoinedGroups[0].account;
          }
        }
      }
    });
  }

  loadDealsForManual(): void {
    this.dealsLoading = true;
    this.api.getDeals(undefined, 'active').subscribe({
      next: (deals) => {
        this.availableDeals = deals || [];
        this.dealsLoading = false;
      },
      error: () => {
        this.dealsLoading = false;
      }
    });
  }

  get filteredAvailableDeals(): DealItem[] {
    if (!this.dealSearchQuery.trim()) {
      return this.availableDeals.slice(0, 50);
    }
    const q = this.dealSearchQuery.toLowerCase();
    return this.availableDeals.filter(d => 
      (d.title || '').toLowerCase().includes(q) || 
      (d.niche || '').toLowerCase().includes(q)
    ).slice(0, 50);
  }

  onManualGroupSelect(url: string): void {
    this.manualForm.group_url = url;
    const match = this.activeJoinedGroups.find(g => g.url === url);
    if (match && match.account) {
      this.manualForm.account = match.account;
    }
  }

  onDealSelect(dealId: string): void {
    this.selectedDealId = dealId;
    const deal = this.availableDeals.find(d => d.id === dealId);
    if (!deal) return;
    this.selectedDeal = deal;

    // Tự động sinh Caption chuyên nghiệp
    const priceFormatted = (deal.price || 0).toLocaleString('vi-VN');
    const origPriceFormatted = (deal.orig_price || 0).toLocaleString('vi-VN');
    this.manualForm.caption = `🔥 DEAL HOT GIẢM SỐC HÔM NAY!\n⚡ ${deal.title}\n💰 Giá sale chỉ: ${priceFormatted}đ (Giảm ${deal.discount || 0}% so với gốc ${origPriceFormatted}đ)\n⭐ Đánh giá: ${deal.rating || 5.0}/5.0 • Đã bán ${deal.sold || 0} lượt\n\nNhanh tay săn ngay trong khung giờ vàng, số lượng ưu đãi có hạn anh em ơi! 👇`;

    // Tự động sinh Comment link affiliate & phễu
    const affLink = deal.aff_url || deal.url || '';
    this.manualForm.comment = `👉 Link săn deal chính hãng Shopee tại đây: ${affLink}\n🚀 Tham gia Telegram nhận deal VIP & mã 0Đ sớm nhất: https://t.me/san_sale_shopee`;

    // Gán ảnh nếu có
    if (deal.image_path) {
      this.manualForm.image_path = deal.image_path;
    } else if (deal.image) {
      this.manualForm.image_path = deal.image;
    }

    // Tự động tìm nhóm có ngách phù hợp
    if (deal.niche && this.activeJoinedGroups.length > 0) {
      const match = this.activeJoinedGroups.find(g => 
        (g.niche || '').toLowerCase().includes((deal.niche || '').toLowerCase()) ||
        g.kind === 'dealhunt'
      );
      if (match) {
        this.manualForm.group_url = match.url;
        if (match.account) {
          this.manualForm.account = match.account;
        }
      }
    }
    this.msg.info(`Đã áp dụng thông tin deal "${deal.title.slice(0, 30)}..." vào bài viết!`);
  }

  clearDealSelection(): void {
    this.selectedDealId = '';
    this.selectedDeal = null;
    this.manualForm.caption = '🔥 DEAL HOT GIẢM SỐC HÔM NAY!\nSăn ngay giá siêu hời chỉ trong khung giờ vàng, số lượng có hạn anh em ơi!';
    this.manualForm.comment = '👉 Link mua sản phẩm chính hãng: https://s.shopee.vn/test-deal-bot\nTham gia nhóm Telegram nhận deal sớm: https://t.me/san_sale_shopee';
    this.manualForm.image_path = '';
  }

  runManualPost(): void {
    if (!this.manualForm.group_url) {
      this.msg.warning('Vui lòng nhập hoặc chọn link nhóm Facebook!');
      return;
    }
    if (!this.manualForm.caption) {
      this.msg.warning('Vui lòng nhập nội dung bài viết (caption)!');
      return;
    }

    this.manualLoading = true;
    this.manualResult = null;

    this.api.testPost(this.manualForm).subscribe({
      next: (res) => {
        this.manualLoading = false;
        this.manualResult = res;
        if (res.success) {
          this.msg.success(res.message || 'Thực hiện đăng bài thành công!');
          // Tự động refresh lịch đăng bài
          this.fetchPosts();
        } else {
          this.msg.warning(res.message || 'Thao tác hoàn tất nhưng có cảnh báo.');
        }
      },
      error: (err) => {
        this.manualLoading = false;
        const msg = err?.error?.detail || 'Lỗi khi gọi API đăng bài!';
        this.msg.error(msg);
      }
    });
  }

  // ==========================================
  // --- AUTO PILOT LOGIC ---
  // ==========================================
  runFullPipelineAction(): void {
    if (!confirm('Khởi chạy toàn bộ quy trình: Quét deal mới -> Lập lịch ngày hôm nay -> Đăng các bài đến giờ?')) return;
    this.pipelineLoading = true;
    this.pipelineResult = null;

    this.api.runFullPipeline().subscribe({
      next: (res) => {
        this.pipelineLoading = false;
        this.pipelineResult = res;
        this.msg.success(res.message || 'Đã kích hoạt toàn bộ pipeline tự động!');
        setTimeout(() => {
          this.fetchPosts();
          this.fetchGroups();
        }, 2000);
      },
      error: (err) => {
        this.pipelineLoading = false;
        const msg = err?.error?.detail || 'Lỗi khi chạy Full Pipeline!';
        this.msg.error(msg);
      }
    });
  }
}


