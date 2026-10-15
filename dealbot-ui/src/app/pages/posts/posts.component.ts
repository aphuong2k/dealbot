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
    NzInputModule
  ],
  templateUrl: './posts.component.html',
  styleUrls: ['./posts.component.css']
})
export class PostsComponent implements OnInit {
  posts: PostItem[] = [];
  loading = false;
  planLoading = false;
  runDueLoading = false;

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

  triggerPlan(): void {
    this.planLoading = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.planLoading = false;
        this.msg.success(res.message);
        this.fetchPosts();
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
        setTimeout(() => this.fetchPosts(), 3000);
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

