import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, PostItem, TestPostPayload, TestPostResult, GroupItem } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzTabsModule } from 'ng-zorro-antd/tabs';

@Component({
  selector: 'app-posts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzSelectModule,
    NzTagModule,
    NzSpinModule,
    NzModalModule,
    NzSwitchModule,
    NzInputModule,
    NzTabsModule
  ],
  templateUrl: './posts.component.html',
  styleUrls: ['./posts.component.css']
})
export class PostsComponent implements OnInit {
  posts: PostItem[] = [];
  loading = false;
  planLoading = false;
  runDueLoading = false;

  // Lịch sử đăng bài
  selectedTabIndex = 0;
  activePostTab: 'queue' | 'history' = 'queue';
  historyPosts: PostItem[] = [];
  historyLoading = false;
  clearingHistory = false;
  deletingPostId: number | null = null;

  selectedStatus = '';
  selectedAccount = '';

  selectedPostForPreview: PostItem | null = null;
  previewModalVisible = false;

  // Test Post State
  testModalVisible = false;
  testLoading = false;
  testResult: TestPostResult | null = null;
  activeGroups: GroupItem[] = [];
  testForm: TestPostPayload = {
    account: 'nick_a',
    group_url: '',
    caption: '🔥 DEAL HOT GIẢM SỐC HÔM NAY!\nSăn ngay giá siêu hời chỉ trong khung giờ vàng, số lượng có hạn anh em ơi!',
    comment: '👉 Link mua sản phẩm chính hãng: https://s.shopee.vn/test-deal-bot\nTham gia nhóm Telegram nhận deal sớm: https://t.me/san_sale_shopee',
    dry_run: true,
    image_path: ''
  };

  statusOptions = [
    { label: 'Tất cả trạng thái', value: '' },
    { label: 'Đang xếp hàng (Queued)', value: 'queued' },
    { label: 'Đã đăng (Done)', value: 'done' },
    { label: 'Chờ admin duyệt (Pending)', value: 'pending_approval' },
    { label: 'Thất bại (Failed)', value: 'failed' },
    { label: 'Bỏ qua (Skipped)', value: 'skipped' }
  ];

  accountOptions = [
    { label: 'Tất cả nick', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchPosts();
    this.loadHistory();
  }

  fetchPosts(): void {
    this.loading = true;
    this.api.getPosts(this.selectedStatus || undefined, this.selectedAccount || undefined).subscribe({
      next: (data) => {
        this.posts = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải lịch trình bài đăng!');
      }
    });
  }

  loadHistory(): void {
    this.historyLoading = true;
    this.api.getPostsHistory(undefined, 50).subscribe({
      next: (data) => {
        this.historyPosts = data;
        this.historyLoading = false;
      },
      error: () => {
        this.historyLoading = false;
        this.msg.error('Không thể tải lịch sử đăng bài!');
      }
    });
  }

  clearHistory(): void {
    if (!confirm('Bạn có chắc chắn muốn xóa sạch toàn bộ lịch sử các bài đã đăng / đã xử lý? (Các bài đang chờ đăng trong hàng đợi sẽ được giữ nguyên an toàn)')) {
      return;
    }
    this.clearingHistory = true;
    this.api.clearPostsHistory().subscribe({
      next: (res) => {
        this.clearingHistory = false;
        this.msg.success(res.message || 'Đã dọn sạch lịch sử đăng bài!');
        this.loadHistory();
      },
      error: () => {
        this.clearingHistory = false;
        this.msg.error('Lỗi khi xóa lịch sử đăng bài!');
      }
    });
  }

  deleteSinglePost(post: PostItem, fromHistory = false): void {
    if (!confirm(`Bạn có chắc muốn xóa bài đăng #${post.id} (${post.group_name || post.group_url})?`)) {
      return;
    }
    this.deletingPostId = post.id;
    this.api.deletePost(post.id).subscribe({
      next: (res) => {
        this.deletingPostId = null;
        this.msg.success(res.message || `Đã xóa bài đăng #${post.id}`);
        if (fromHistory) {
          this.historyPosts = this.historyPosts.filter(p => p.id !== post.id);
        } else {
          this.posts = this.posts.filter(p => p.id !== post.id);
        }
      },
      error: () => {
        this.deletingPostId = null;
        this.msg.error('Lỗi khi xóa bài đăng!');
      }
    });
  }

  formatTime(ts?: number): string {
    if (!ts) return '-';
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString('vi-VN');
  }

  triggerPlan(): void {
    this.planLoading = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.planLoading = false;
        this.msg.success(res.message);
        this.fetchPosts();
        this.loadHistory();
      },
      error: () => {
        this.planLoading = false;
        this.msg.error('Lỗi khi lập lịch hôm nay!');
      }
    });
  }

  triggerRunDue(): void {
    this.runDueLoading = true;
    this.api.runDuePosts().subscribe({
      next: (res) => {
        this.runDueLoading = false;
        this.msg.success(res.message);
        setTimeout(() => {
          this.fetchPosts();
          this.loadHistory();
        }, 3000);
      },
      error: () => {
        this.runDueLoading = false;
        this.msg.error('Lỗi khi kích hoạt phiên đăng bài!');
      }
    });
  }

  runningPostId: number | null = null;

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

  viewPost(post: PostItem): void {
    this.selectedPostForPreview = post;
    this.previewModalVisible = true;
  }

  closePreview(): void {
    this.previewModalVisible = false;
    this.selectedPostForPreview = null;
  }

  // --- TEST POST MODAL LOGIC ---
  openTestModal(): void {
    this.testModalVisible = true;
    this.testResult = null;
    // Tải danh sách nhóm đang hoạt động để người dùng chọn nhanh nếu chưa có
    if (this.activeGroups.length === 0) {
      this.api.getGroups().subscribe({
        next: (groups) => {
          this.activeGroups = groups.filter(g => g.status === 'joined' || g.status === 'approved' || g.status === 'candidate');
          if (this.activeGroups.length > 0 && !this.testForm.group_url) {
            this.testForm.group_url = this.activeGroups[0].url;
            if (this.activeGroups[0].account) {
              this.testForm.account = this.activeGroups[0].account;
            }
          }
        }
      });
    }
  }

  closeTestModal(): void {
    this.testModalVisible = false;
  }

  onGroupSelect(url: string): void {
    this.testForm.group_url = url;
    const match = this.activeGroups.find(g => g.url === url);
    if (match && match.account) {
      this.testForm.account = match.account;
    }
  }

  runTestPost(): void {
    if (!this.testForm.group_url) {
      this.msg.warning('Vui lòng nhập hoặc chọn link nhóm Facebook!');
      return;
    }
    if (!this.testForm.caption) {
      this.msg.warning('Vui lòng nhập nội dung bài viết (caption)!');
      return;
    }

    this.testLoading = true;
    this.testResult = null;

    this.api.testPost(this.testForm).subscribe({
      next: (res) => {
        this.testLoading = false;
        this.testResult = res;
        if (res.success) {
          this.msg.success(res.message || 'Thực hiện test đăng bài thành công!');
        } else {
          this.msg.warning(res.message || 'Thao tác hoàn tất nhưng có cảnh báo.');
        }
      },
      error: (err) => {
        this.testLoading = false;
        const msg = err?.error?.detail || 'Lỗi khi gọi API test đăng bài!';
        this.msg.error(msg);
      }
    });
  }
}

