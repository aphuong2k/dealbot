import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, GroupItem, ScannedGroup, EvaluatedGroup, PostItem, TestPostPayload, TestPostResult, DealItem, GradualPostingState } from '../../services/api.service';
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
export class GroupsComponent implements OnInit, OnDestroy {
  groups: GroupItem[] = [];
  loading = false;
  discoverLoading = false;

  // --- GRADUAL AUTO-POSTING STATE (Inspired by auto-aff) ---
  gradualPostingState: GradualPostingState = {
    is_running: false,
    total_target: 0,
    completed: 0,
    current_group: '',
    current_deal: '',
    current_account: '',
    next_post_time: null,
    remaining_delay: 0,
    delay_seconds: 60,
    status: 'IDLE',
    history: []
  };
  gradualPollingTimer: any = null;
  selectedGroupUrls: string[] = [];
  gradualDelaySeconds: number = 60;
  gradualMaxGroups: number = 5;
  selectedGradualAccount: string = '';
  gradualDryRun: boolean = false;
  gradualLinkMode: 'caption' | 'comment' = 'caption';
  matchedDeals: { [url: string]: any } = {};
  postingSingleGroup: { [url: string]: boolean } = {};

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
  selectedTargetType: 'posting' | 'lazada_hunter' | 'all' = 'posting';

  accountOptions = [
    { label: 'Chưa gán', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  targetTypeOptions = [
    { label: '📢 Nhóm Đăng Bài (Posting)', value: 'posting' },
    { label: '🔍 Nhóm Quét Giá Lazada (Hunter)', value: 'lazada_hunter' },
    { label: '🌐 Tất cả nhóm', value: 'all' }
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

  // --- BLACKLIST & AUTO-LEAVE STATE ---
  blacklistedGroups: GroupItem[] = [];
  blacklistLoading = false;
  blacklistCandidates: any[] = [];
  blacklistCandidatesLoading = false;
  blacklistCandidatesModalVisible = false;
  cleanBlacklistLoading = false;
  banningGroupUrl = '';
  unbanningGroupUrl = '';


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
    this.fetchGradualPostingStatus();
    this.loadMatchedDeals();
  }

  ngOnDestroy(): void {
    if (this.gradualPollingTimer) {
      clearInterval(this.gradualPollingTimer);
      this.gradualPollingTimer = null;
    }
  }

  // --- GRADUAL AUTO-POSTING METHODS (Inspired by auto-aff) ---
  fetchGradualPostingStatus(): void {
    this.api.getGradualPostingStatus().subscribe({
      next: (res) => {
        this.gradualPostingState = res;
        if (res.is_running && !this.gradualPollingTimer) {
          this.gradualPollingTimer = setInterval(() => this.fetchGradualPostingStatus(), 1500);
        } else if (!res.is_running && this.gradualPollingTimer) {
          clearInterval(this.gradualPollingTimer);
          this.gradualPollingTimer = null;
          this.fetchGroups();
          this.fetchPosts();
        }
      },
      error: (err) => console.error('Lỗi nạp trạng thái đăng bài dần:', err)
    });
  }

  startSequentialPosting(): void {
    if (this.gradualPostingState.is_running) {
      this.msg.info('Tiến trình đăng bài đang chạy, vui lòng chờ hoặc bấm Dừng!');
      return;
    }

    let targetUrls = [...this.selectedGroupUrls];
    if (targetUrls.length === 0) {
      const activePostingGroups = this.groups.filter(g => (g.status === 'joined' || g.status === 'approved') && g.target_type !== 'lazada_hunter');
      if (activePostingGroups.length === 0) {
        this.msg.warning('Không có nhóm Đăng Bài Bán Hàng nào ở trạng thái ĐÃ VÀO (Joined)!');
        return;
      }
      this.selectAllJoinedGroups();
      targetUrls = this.selectedGroupUrls;
    }

    const delay = this.gradualDelaySeconds || 60;
    const accLabel = this.selectedGradualAccount ? ` bằng [${this.selectedGradualAccount}]` : ' (Tự động luân phiên)';
    const modeLabel = this.gradualLinkMode === 'comment' ? ' (Link để ở comment)' : ' (Link trong bài viết)';
    this.msg.info(`Đang khởi động đăng bài tuần tự vào ${targetUrls.length} nhóm (nhịp nghỉ ${delay}s)${accLabel}${modeLabel}...`);

    this.api.startGradualPosting({
      group_urls: targetUrls,
      delay_seconds: delay,
      account: this.selectedGradualAccount || undefined,
      dry_run: this.gradualDryRun,
      link_in_comment: this.gradualLinkMode === 'comment'
    }).subscribe({
      next: (res) => {
        this.msg.success(res.message || 'Đã khởi động tiến trình đăng bài tuần tự!');
        this.fetchGradualPostingStatus();
      },
      error: (err) => this.msg.error(err?.error?.detail || err?.message || 'Lỗi khởi động đăng bài!')
    });
  }

  stopGradualPosting(): void {
    this.api.stopGradualPosting().subscribe({
      next: (res) => {
        this.msg.info(res.message || 'Đã gửi tín hiệu dừng chu trình đăng bài!');
        this.fetchGradualPostingStatus();
      },
      error: (err) => this.msg.error(err?.message || 'Lỗi khi gửi yêu cầu dừng!')
    });
  }

  postSingleGroupDirect(group: GroupItem): void {
    if (group.target_type === 'lazada_hunter') {
      this.msg.warning('Đây là nhóm chuyên Quét Giá Thị Trường Lazada, không dùng để đăng bài bán hàng!');
      return;
    }
    const url = group.url;
    this.postingSingleGroup[url] = true;
    const acc = this.selectedGradualAccount || group.account || undefined;
    const accLabel = acc ? ` (bằng ${acc})` : '';
    this.msg.info(`Đang đăng bài vào nhóm [${group.name || url}]${accLabel}...`);

    this.api.postSingleGroup({
      group_url: url,
      account: acc,
      dry_run: this.gradualDryRun,
      link_in_comment: this.gradualLinkMode === 'comment'
    }).subscribe({
      next: (res) => {
        this.postingSingleGroup[url] = false;
        this.msg.success(res.message || `Đã đăng bài thành công vào nhóm [${group.name}]!`);
        this.fetchGroups();
        this.fetchPosts();
      },
      error: (err) => {
        this.postingSingleGroup[url] = false;
        const msg = err?.error?.detail || err?.message || 'Lỗi khi đăng bài';
        this.msg.error(`Lỗi đăng bài [${group.name}]: ${msg}`);
      }
    });
  }

  loadMatchedDeals(): void {
    this.api.getGroupMatchedDeals().subscribe({
      next: (data) => this.matchedDeals = data || {},
      error: (err) => console.error('Lỗi tải sản phẩm khớp chuẩn:', err)
    });
  }

  // --- GROUP SELECTION METHODS ---
  isGroupSelected(url: string): boolean {
    return this.selectedGroupUrls.includes(url);
  }

  toggleGroupSelect(url: string): void {
    const idx = this.selectedGroupUrls.indexOf(url);
    if (idx > -1) {
      this.selectedGroupUrls.splice(idx, 1);
    } else {
      this.selectedGroupUrls.push(url);
    }
  }

  isAllGroupsSelected(): boolean {
    const targetGroups = this.groups.filter(g => (g.status === 'joined' || g.status === 'approved') && g.target_type !== 'lazada_hunter');
    if (targetGroups.length === 0) return false;
    return targetGroups.every(g => this.selectedGroupUrls.includes(g.url));
  }

  toggleSelectAllGroups(): void {
    const targetGroups = this.groups.filter(g => (g.status === 'joined' || g.status === 'approved') && g.target_type !== 'lazada_hunter');
    if (this.isAllGroupsSelected()) {
      const targetUrls = new Set(targetGroups.map(g => g.url));
      this.selectedGroupUrls = this.selectedGroupUrls.filter(u => !targetUrls.has(u));
    } else {
      const newUrls = new Set(this.selectedGroupUrls);
      targetGroups.forEach(g => newUrls.add(g.url));
      this.selectedGroupUrls = Array.from(newUrls);
    }
  }

  selectAllJoinedGroups(): void {
    const targetGroups = this.groups.filter(g => (g.status === 'joined' || g.status === 'approved') && g.target_type !== 'lazada_hunter');
    this.selectedGroupUrls = targetGroups.map(g => g.url);
    this.msg.info(`Đã chọn toàn bộ ${this.selectedGroupUrls.length} nhóm Đăng Bài đã tham gia!`);
  }

  deselectAllGroups(): void {
    this.selectedGroupUrls = [];
  }


  fetchGroups(): void {
    this.loading = true;
    const statusParam = this.selectedTab === 'all' ? undefined : this.selectedTab;
    const accountParam = this.selectedAccountFilter === 'all' ? undefined : this.selectedAccountFilter;
    const targetTypeParam = this.selectedTargetType === 'all' ? undefined : this.selectedTargetType;
    this.api.getGroups(statusParam, this.selectedKind || undefined, this.searchQuery || undefined, accountParam, targetTypeParam).subscribe({
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

  toggleTargetType(g: GroupItem): void {
    const newTarget = g.target_type === 'lazada_hunter' ? 'posting' : 'lazada_hunter';
    this.api.updateGroup(g.url, { target_type: newTarget }).subscribe({
      next: () => {
        g.target_type = newTarget;
        const label = newTarget === 'lazada_hunter' ? 'Nhóm Quét Giá Lazada' : 'Nhóm Đăng Bài Bán Hàng';
        this.msg.success(`Đã chuyển nhóm sang "${label}" thành công!`);
        this.fetchGroups();
      },
      error: () => this.msg.error('Lỗi khi chuyển mục đích nhóm!')
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
    if (this.selectedTab === 'banned') {
      this.fetchBlacklist();
    }
  }

  get bannedGroups(): GroupItem[] {
    return this.groups.filter(g => g.status === 'banned');
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
        this.blacklistedGroups = this.blacklistedGroups.filter(item => item.url !== g.url);
      },
      error: (err) => {
        this.msg.error(err?.error?.detail || 'Lỗi khi xóa group!');
      }
    });
  }

  // --- BLACKLIST & AUTO-LEAVE METHODS ---
  fetchBlacklist(): void {
    this.blacklistLoading = true;
    this.api.getBlacklistedGroups().subscribe({
      next: (groups) => {
        this.blacklistedGroups = groups || [];
        this.blacklistLoading = false;
      },
      error: () => {
        this.blacklistLoading = false;
        this.msg.error('Không thể tải danh sách đen các nhóm!');
      }
    });
  }

  scanAndCleanBlacklist(autoLeaveFb: boolean = true): void {
    this.cleanBlacklistLoading = true;
    const leaveLabel = autoLeaveFb ? 'đồng thời rời nhóm trên Facebook' : 'chỉ đánh dấu trong hệ thống';
    this.msg.info(`Đang quét dọn các nhóm vi phạm (${leaveLabel})...`);

    this.api.scanAndCleanBlacklist({ auto_leave_fb: autoLeaveFb, max_groups: 5 }).subscribe({
      next: (res) => {
        this.cleanBlacklistLoading = false;
        const cleaned = res.cleaned_count || 0;
        const total = res.total_bad_found || 0;
        if (cleaned > 0) {
          this.msg.success(`Đã phát hiện ${total} nhóm vi phạm, thanh lọc và out thành công ${cleaned} nhóm vào Danh Sách Đen!`);
        } else if (total > 0) {
          this.msg.warning(`Tìm thấy ${total} nhóm vi phạm nhưng không có nhóm nào đủ điều kiện out đợt này.`);
        } else {
          this.msg.info('✨ Tuyệt vời! Không phát hiện nhóm nào vi phạm (cấm đăng/pending duyệt/lỗi liên tiếp).');
        }
        this.fetchGroups();
        this.fetchBlacklist();
        if (this.blacklistCandidatesModalVisible) {
          this.blacklistCandidatesModalVisible = false;
        }
      },
      error: (err) => {
        this.cleanBlacklistLoading = false;
        this.msg.error(err?.error?.detail || err?.message || 'Lỗi khi quét dọn nhóm vi phạm!');
      }
    });
  }

  openBlacklistCandidatesModal(): void {
    this.blacklistCandidatesModalVisible = true;
    this.blacklistCandidatesLoading = true;
    this.blacklistCandidates = [];
    this.api.getBlacklistCandidates(3, 2).subscribe({
      next: (candidates) => {
        this.blacklistCandidates = candidates || [];
        this.blacklistCandidatesLoading = false;
      },
      error: () => {
        this.blacklistCandidatesLoading = false;
        this.msg.error('Lỗi khi tải danh sách nhóm có nguy cơ vi phạm!');
      }
    });
  }

  closeBlacklistCandidatesModal(): void {
    this.blacklistCandidatesModalVisible = false;
  }

  banSingleGroup(g: GroupItem, autoLeave: boolean = true): void {
    this.banningGroupUrl = g.url;
    this.api.banGroupManual(g.url, 'Người dùng đưa vào Danh Sách Đen thủ công', autoLeave, g.account).subscribe({
      next: (res) => {
        this.banningGroupUrl = '';
        this.msg.success(`Đã đưa nhóm [${g.name || g.url}] vào Danh Sách Đen thành công!`);
        this.fetchGroups();
        this.fetchBlacklist();
      },
      error: (err) => {
        this.banningGroupUrl = '';
        this.msg.error(err?.error?.detail || err?.message || 'Lỗi khi chặn nhóm!');
      }
    });
  }

  unbanSingleGroup(g: GroupItem): void {
    this.unbanningGroupUrl = g.url;
    this.api.unbanGroup(g.url, 'candidate').subscribe({
      next: (res) => {
        this.unbanningGroupUrl = '';
        this.msg.success(`Đã mở khóa nhóm [${g.name || g.url}] khỏi Danh Sách Đen (chuyển về Candidate)!`);
        this.fetchGroups();
        this.fetchBlacklist();
      },
      error: (err) => {
        this.unbanningGroupUrl = '';
        this.msg.error(err?.error?.detail || err?.message || 'Lỗi khi gỡ chặn nhóm!');
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

  get joinedGroups(): GroupItem[] {
    return this.groups.filter(g => (g.status === 'joined' || g.status === 'approved') && g.target_type !== 'lazada_hunter');
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
    this.api.getGroups(undefined, undefined, undefined, undefined, 'posting').subscribe({
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


