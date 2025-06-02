import os
import shutil
from datetime import datetime
import logging

# 如果此模組作為獨立腳本運行，配置基礎日誌記錄
# 如果被其他已配置日誌的模組導入，則此處的配置可能不會生效（取決於導入順序和配置方式）
if __name__ == "__main__" or not logging.getLogger().hasHandlers(): # 僅在未配置處理程序時配置
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])

logger = logging.getLogger(__name__)

def backup_directory(source_dir: str, backup_root_dir: str, backup_prefix: str = "backup") -> tuple[bool, str | None]:
    """
    將指定的來源資料夾備份到備份根目錄下一個帶時間戳的子資料夾中。

    Args:
        source_dir (str): 要備份的來源資料夾路徑。
        backup_root_dir (str): 存放所有備份的根資料夾路徑。
        backup_prefix (str): 備份資料夾名稱的前綴。

    Returns:
        tuple[bool, str | None]:
            一個元組 (success: bool, backup_path: str | None)。
            如果成功，success 為 True，backup_path 是實際的備份路徑。
            如果失敗，success 為 False，backup_path 為 None。
    """
    logger.info(f"備份請求：來源='{source_dir}', 備份根目錄='{backup_root_dir}', 前綴='{backup_prefix}'")

    if not os.path.exists(source_dir) or not os.path.isdir(source_dir):
        logger.error(f"備份錯誤：來源資料夾 '{source_dir}' 不存在或不是一個有效的目錄。")
        print(f"❌ 備份錯誤：來源資料夾 '{source_dir}' 無效或不存在。")
        return False, None

    if not os.listdir(source_dir):
        logger.warning(f"備份提示：來源資料夾 '{source_dir}' 為空。仍將執行備份操作以記錄此狀態。")
        # 允許備份空資料夾

    if not os.path.exists(backup_root_dir):
        try:
            os.makedirs(backup_root_dir, exist_ok=True)
            logger.info(f"備份根目錄 '{backup_root_dir}' 已成功創建。")
            print(f"ℹ️ 備份根目錄 '{backup_root_dir}' 已創建。")
        except Exception as e_mkdir:
            logger.error(f"備份錯誤：無法創建備份根目錄 '{backup_root_dir}': {e_mkdir}")
            print(f"❌ 備份錯誤：無法創建備份根目錄 '{backup_root_dir}' ({e_mkdir})。")
            return False, None
    elif not os.path.isdir(backup_root_dir):
        logger.error(f"備份錯誤：指定的備份根目錄 '{backup_root_dir}' 已存在但不是一個目錄。")
        print(f"❌ 備份錯誤：備份目標 '{backup_root_dir}' 不是一個有效的目錄。")
        return False, None


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_instance_name = f"{backup_prefix}_{timestamp}"
    backup_instance_path = os.path.join(backup_root_dir, backup_instance_name)

    try:
        shutil.copytree(source_dir, backup_instance_path)
        logger.info(f"成功將 '{source_dir}' 備份至 '{backup_instance_path}'。")
        print(f"✅ 成功將 '{os.path.basename(source_dir)}' 備份至 '{backup_instance_name}' (位於 {backup_root_dir})。")
        return True, backup_instance_path
    except FileExistsError: # 幾乎不可能發生，因為有時間戳，但以防萬一
        logger.error(f"備份錯誤：目標備份路徑 '{backup_instance_path}' 已存在。")
        print(f"❌ 備份錯誤：目標備份路徑 '{backup_instance_path}' 已存在。")
        return False, None
    except Exception as e:
        logger.error(f"備份 '{source_dir}' 到 '{backup_instance_path}' 失敗: {e}", exc_info=True)
        print(f"❌ 備份 '{os.path.basename(source_dir)}' 失敗: {e}")
        return False, None

if __name__ == '__main__':
    # 此區塊用於直接測試 backup_utils.py
    print("正在測試 backup_utils.py...")

    # 為了能在任何環境下測試，創建臨時的 source 和 backup_root
    # 使用 os.getcwd() 來確保路徑是相對於當前工作目錄
    current_working_directory = os.getcwd()
    test_source_dir = os.path.join(current_working_directory, "temp_source_for_backup_test")
    test_backup_root = os.path.join(current_working_directory, "temp_backup_root_test")

    try:
        # 創建測試源目錄和文件
        os.makedirs(test_source_dir, exist_ok=True)
        print(f"\n創建臨時測試源目錄: {test_source_dir}")
        with open(os.path.join(test_source_dir, "file1.txt"), "w") as f:
            f.write("這是測試文件內容1。")
        os.makedirs(os.path.join(test_source_dir, "subdir_test"), exist_ok=True)
        with open(os.path.join(test_source_dir, "subdir_test", "file2.txt"), "w") as f:
            f.write("這是子目錄中的測試文件內容2。")

        # 執行備份
        print(f"\n嘗試將 '{test_source_dir}' 備份到 '{test_backup_root}' (前綴: my_project_backup)...")
        success, backup_path_result = backup_directory(test_source_dir, test_backup_root, backup_prefix="my_project_backup")

        if success and backup_path_result:
            print(f"\n測試備份成功！")
            print(f"  完整備份路徑: {backup_path_result}")

            # 驗證備份內容
            print("\n  驗證備份內容...")
            expected_file1 = os.path.join(backup_path_result, "file1.txt")
            expected_file2 = os.path.join(backup_path_result, "subdir_test", "file2.txt")

            if os.path.exists(expected_file1):
                 print(f"    ✅ file1.txt 存在於備份中: {expected_file1}")
            else:
                 print(f"    ❌ 驗證錯誤：file1.txt 未在備份中找到！路徑: {expected_file1}")

            if os.path.exists(expected_file2):
                 print(f"    ✅ subdir_test/file2.txt 存在於備份中: {expected_file2}")
            else:
                 print(f"    ❌ 驗證錯誤：subdir_test/file2.txt 未在備份中找到！路徑: {expected_file2}")
        else:
            print("\n測試備份失敗。請檢查上面的日誌輸出。")

    except Exception as e_test:
        print(f"\n執行測試時發生錯誤: {e_test}")
    finally:
        # 清理臨時測試目錄和文件
        if os.path.exists(test_source_dir):
            shutil.rmtree(test_source_dir)
            print(f"\n已清理臨時測試源目錄: {test_source_dir}")
        if os.path.exists(test_backup_root):
            shutil.rmtree(test_backup_root)
            print(f"已清理臨時測試備份根目錄: {test_backup_root}")

        print("\nbackup_utils.py 測試執行完畢。")
